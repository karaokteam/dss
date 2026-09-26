"""Triton Python-backend model: one JPEG (as uint8 bytes) in, up to 300 boxes (x1, y1, x2, y2, score, class) out.

The TensorRT engine is read from model.engine next to this file. The JPEG is decoded on the CPU; letterboxing to
1920x1920, the engine and NMS run on the GPU.
Each Triton instance of this model is a separate process with its own TensorRT context.
Tensors go in and out through DLPack: the backend's NumPy bridge does not work with NumPy 2.
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# The Python backend ignores PYTHONPATH; start_server.sh passes extra package folders in SITE_PACKAGES instead.
sys.path[:0] = [p for p in os.environ.get('SITE_PACKAGES', '').split(':') if p]

import tensorrt as trt  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
import triton_python_backend_utils as pb_utils  # noqa: E402
from torch.utils.dlpack import to_dlpack  # noqa: E402
from torchvision.io import decode_jpeg  # noqa: E402
from ultralytics.utils.nms import non_max_suppression  # noqa: E402

SIZE = 1920
MAX_BOXES = 300
CONFIDENCE = 0.25


class TritonPythonModel:
    def initialize(self, args):
        torch.cuda.set_device(int(args['model_instance_device_id']))

        data = open(os.path.join(os.path.dirname(__file__), 'model.engine'), 'rb').read()
        metadata_length = int.from_bytes(data[:4], byteorder='little')   # Ultralytics stores metadata in front
        engine = trt.Runtime(trt.Logger(trt.Logger.WARNING)).deserialize_cuda_engine(data[4 + metadata_length:])
        self.context = engine.create_execution_context()
        names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
        self.input_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
        self.output_name = next(n for n in names if n != self.input_name)
        self.input_dtype = torch.float16 if engine.get_tensor_dtype(self.input_name) == trt.float16 else torch.float32
        self.stream = torch.cuda.Stream()
        self.decoder = ThreadPoolExecutor(8)

    def execute(self, requests):
        # with dynamic batching Triton hands us several requests at once: run them as one batch
        # each request is one JPEG file as a uint8 tensor of shape [1, file size]
        jpegs = [torch.from_dlpack(pb_utils.get_input_tensor_by_name(r, 'image').to_dlpack())[0].clone() for r in requests]

        with torch.cuda.stream(self.stream):
            boxes, count = self.detect(jpegs)

        responses = []
        for i in range(len(requests)):
            outputs = [pb_utils.Tensor.from_dlpack('boxes', to_dlpack(boxes[i:i + 1])),
                       pb_utils.Tensor.from_dlpack('count', to_dlpack(count[i:i + 1]))]
            responses.append(pb_utils.InferenceResponse(outputs))
        return responses

    def detect(self, jpegs):
        # The GPU decoder (nvJPEG) rejects some of these JPEGs, so decode on the CPU, several at a time
        images = [image.cuda() for image in self.decoder.map(decode_jpeg, jpegs)]
        batch, scales, pads = self.letterbox(images)
        detections = non_max_suppression(self.run_engine(batch), conf_thres=CONFIDENCE, iou_thres=0.7, max_det=MAX_BOXES)

        boxes = torch.zeros((len(jpegs), MAX_BOXES, 6), dtype=torch.float32)
        count = torch.zeros((len(jpegs), 1), dtype=torch.int32)
        for i, d in enumerate(detections):
            d[:, [0, 2]] = (d[:, [0, 2]] - pads[i][0]) / scales[i]   # back to original image pixels
            d[:, [1, 3]] = (d[:, [1, 3]] - pads[i][1]) / scales[i]
            boxes[i, :len(d)] = d.cpu()
            count[i] = len(d)
        return boxes, count

    def letterbox(self, images):
        """Fit each image into 1920x1920 and pad with grey, as Ultralytics does."""
        batch = torch.full((len(images), 3, SIZE, SIZE), 114, dtype=torch.uint8, device='cuda')
        scales, pads = [], []
        for i, image in enumerate(images):
            h, w = image.shape[1:]
            scale = min(SIZE / h, SIZE / w)
            new_h, new_w = round(h * scale), round(w * scale)
            top, left = (SIZE - new_h) // 2, (SIZE - new_w) // 2
            resized = F.interpolate(image[None].float(), size=(new_h, new_w), mode='bilinear', align_corners=False)
            batch[i, :, top:top + new_h, left:left + new_w] = resized[0].round().clamp(0, 255).to(torch.uint8)
            scales.append(scale)
            pads.append((left, top))
        return batch, scales, pads

    def run_engine(self, batch):
        x = (batch.to(self.input_dtype) / 255).contiguous()
        self.context.set_input_shape(self.input_name, tuple(x.shape))
        output = torch.empty(tuple(self.context.get_tensor_shape(self.output_name)), dtype=torch.float32, device='cuda')
        self.context.set_tensor_address(self.input_name, x.data_ptr())
        self.context.set_tensor_address(self.output_name, output.data_ptr())
        self.context.execute_async_v3(torch.cuda.current_stream().cuda_stream)
        return output

"""Latency and throughput for batch sizes 1-16 (model only, 1920x1920 input). Appends to results/results.json.

    python benchmark.py tensorrt fp16 work/engines/yolo26l_1920_split_fp16.engine
    python benchmark.py pytorch fp16 work/weights/split/yolo26l_1920_split.pt
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

BATCHES = [1, 2, 4, 8, 16]
SIZE = 1920
RESULTS = Path(__file__).parent / 'results' / 'results.json'


def measure(run, iterations):
    """Mean / median / 95th percentile time of run() in ms, after a warm-up."""
    for _ in range(10):
        run()
    torch.cuda.synchronize()
    times = []
    for _ in range(iterations):
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        start.record()
        run()
        end.record()
        torch.cuda.synchronize()
        times.append(start.elapsed_time(end))
    return np.mean(times), np.median(times), np.percentile(times, 95)


def tensorrt_runs(engine_file):
    """Yields (batch, run function) for a TensorRT engine exported by Ultralytics."""
    import tensorrt as trt
    data = Path(engine_file).read_bytes()
    metadata_length = int.from_bytes(data[:4], byteorder='little')   # Ultralytics stores metadata in front
    engine = trt.Runtime(trt.Logger(trt.Logger.WARNING)).deserialize_cuda_engine(data[4 + metadata_length:])
    context = engine.create_execution_context()
    names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
    input_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
    torch_dtype = {trt.float32: torch.float32, trt.float16: torch.float16}
    stream = torch.cuda.current_stream().cuda_stream

    buffers = []   # the engine reads and writes these tensors' memory
    for batch in BATCHES:
        context.set_input_shape(input_name, (batch, 3, SIZE, SIZE))
        buffers.clear()
        for name in names:
            shape = tuple(context.get_tensor_shape(name))
            buffers.append(torch.rand(shape, device='cuda').to(torch_dtype[engine.get_tensor_dtype(name)]))
            context.set_tensor_address(name, buffers[-1].data_ptr())
        yield batch, lambda: context.execute_async_v3(stream)


def pytorch_runs(checkpoint, precision):
    from ultralytics import YOLO
    dtype = torch.float16 if precision == 'fp16' else torch.float32
    model = YOLO(checkpoint).model.fuse().eval().cuda().to(dtype)
    for batch in BATCHES:
        x = torch.rand(batch, 3, SIZE, SIZE, device='cuda', dtype=dtype)
        yield batch, lambda: model(x)


if __name__ == '__main__':
    backend, precision, model_file = sys.argv[1], sys.argv[2], sys.argv[3]
    runs = tensorrt_runs(model_file) if backend == 'tensorrt' else pytorch_runs(model_file, precision)

    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {'latency': [], 'accuracy': []}
    with torch.inference_mode():
        for batch, run in runs:
            mean, median, p95 = measure(run, iterations=100 if batch <= 4 else 50)
            row = {'backend': 'TensorRT' if backend == 'tensorrt' else 'PyTorch', 'precision': precision,
                   'batch': batch, 'mean_ms': mean, 'p50_ms': median, 'p95_ms': p95, 'img_per_s': batch * 1000 / mean}
            results['latency'].append(row)
            print(f'batch {batch:2d}: {mean:6.1f} ms  {row["img_per_s"]:5.0f} images/s')

    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1))

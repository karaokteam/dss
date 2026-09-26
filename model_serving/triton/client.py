"""Send one JPEG to the Triton server and print the vehicles it finds.   python client.py IMAGE"""
import sys

import numpy as np
from tritonclient.grpc import InferenceServerClient, InferInput

CLASSES = ['car', 'van', 'truck', 'bus']

jpeg = np.fromfile(sys.argv[1], dtype=np.uint8)[None]   # the JPEG file as bytes, shape [1, file size]
request = InferInput('image', list(jpeg.shape), 'UINT8')
request.set_data_from_numpy(jpeg)
result = InferenceServerClient('localhost:8001').infer('yolo26l', [request])

count = result.as_numpy('count')[0, 0]
for x1, y1, x2, y2, score, cls in result.as_numpy('boxes')[0, :count]:
    print(f'{CLASSES[int(cls)]:5s} {score:.2f}   {x1:.0f} {y1:.0f} {x2:.0f} {y2:.0f}')

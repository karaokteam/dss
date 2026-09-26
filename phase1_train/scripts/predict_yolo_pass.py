"""One YOLO pass over an image set -> CSV. Mirrored passes flip the image and flip the boxes back."""
import argparse
import functools
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO
from ultralytics.utils import nms

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import config, imagesets, submission  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--weights')
parser.add_argument('--images')
parser.add_argument('--size', type=int)
parser.add_argument('--hflip', action='store_true')
parser.add_argument('--vflip', action='store_true')
parser.add_argument('--half', action='store_true')
parser.add_argument('--out')
args = parser.parse_args()
settings = config.load()['yolo_inference']

# multi-label NMS: a box is kept under every class above the threshold (mAP ranks each class separately)
nms.non_max_suppression = functools.partial(nms.non_max_suppression, multi_label=True)
model = YOLO(args.weights)
ids, files = imagesets.load(args.images)

rows = {}
for start in range(0, len(ids), 32):
    batch = ids[start:start + 32]
    images = [cv2.imread(str(files[i])) for i in batch]
    if args.hflip:
        images = [im[:, ::-1].copy() for im in images]
    if args.vflip:
        images = [im[::-1].copy() for im in images]
    results = model.predict(images, imgsz=args.size, conf=settings['conf'], iou=settings['iou'],
                            max_det=settings['max_det'], half=args.half, verbose=False)

    for image_id, image, result in zip(batch, images, results):
        H, W = image.shape[:2]
        parts = []
        for (x1, y1, x2, y2), score, c in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
            if args.hflip:
                x1, x2 = W - x2, W - x1
            if args.vflip:
                y1, y2 = H - y2, H - y1
            parts.append(f'{model.names[int(c)]} {score:.4f} {round(x1)} {round(y1)} {round(x2 - x1)} {round(y2 - y1)}')
        rows[image_id] = ' '.join(parts) or 'none'

submission.write(Path(args.out), rows)

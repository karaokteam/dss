"""One RF-DETR-L pass over an image set -> CSV (rfdetr environment)."""
import argparse
import gc
import sys
from pathlib import Path

from PIL import Image, ImageOps
from rfdetr import RFDETRLarge
from rfdetr.models.postprocess import PostProcess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import config, imagesets, submission  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--weights')
parser.add_argument('--images')
parser.add_argument('--size', type=int)
parser.add_argument('--hflip', action='store_true')
parser.add_argument('--out')
args = parser.parse_args()
settings = config.load()['rfdetr_inference']

model = RFDETRLarge(pretrain_weights=args.weights, resolution=args.size)
for obj in gc.get_objects():   # rfdetr has no option for the number of boxes per image
    if isinstance(obj, PostProcess):
        obj.num_select = settings['num_select']
names = model.class_names
ids, files = imagesets.load(args.images)

rows = {}
for start in range(0, len(ids), 16):
    batch = ids[start:start + 16]
    images = [Image.open(files[i]).convert('RGB') for i in batch]
    if args.hflip:
        images = [ImageOps.mirror(im) for im in images]
    detections = model.predict(images, threshold=settings['threshold'])
    if len(batch) == 1:   # rfdetr returns a single result instead of a list
        detections = [detections]

    for image_id, image, d in zip(batch, images, detections):
        if args.hflip:
            d.xyxy[:, [0, 2]] = image.width - d.xyxy[:, [2, 0]]
        parts = []
        for (x1, y1, x2, y2), score, c in zip(d.xyxy.tolist(), d.confidence.tolist(), d.class_id.tolist()):
            if c < len(names):   # the head has one extra, unused class slot
                parts.append(f'{names[c]} {score:.4f} {round(x1)} {round(y1)} {round(x2 - x1)} {round(y2 - y1)}')
        rows[image_id] = ' '.join(parts) or 'none'

submission.write(Path(args.out), rows)

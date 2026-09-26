"""Square context crops of every car/van box, the input of train_cls.py (re-implements the Colab notebook step).

Writes work/datasets/dino_crops/{car,van}/*.jpg, crops.csv and splits.csv (10% of the images for validation).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from roketsan import paths  # noqa: E402

OUT = paths.DATASETS / 'dino_crops'

boxes = pd.read_csv(paths.TRAIN_ANNOTATIONS)
boxes['row'] = boxes.index
boxes = boxes[boxes.label.isin(['car', 'van'])]

rows = []
for image_id, group in boxes.groupby('image_id'):
    image = np.asarray(Image.open(paths.TRAIN_IMAGES / f'{image_id}.jpg').convert('RGB'))
    H, W = image.shape[:2]
    cars = group[group.label == 'car']
    median_car_area = (cars.w * cars.h).median()

    for b in group.itertuples():
        if min(b.w, b.h) < 10:
            continue
        # square twice the long side, centred on the box, grey outside the image, original resolution
        side = int(round(2 * max(b.w, b.h)))
        left = int(round(b.x + b.w / 2 - side / 2))
        top = int(round(b.y + b.h / 2 - side / 2))
        crop = np.full((side, side, 3), 114, np.uint8)
        x1, y1, x2, y2 = max(0, left), max(0, top), min(W, left + side), min(H, top + side)
        crop[y1 - top:y2 - top, x1 - left:x2 - left] = image[y1:y2, x1:x2]

        file = f'{b.label}/{image_id}_{b.row}.jpg'
        (OUT / b.label).mkdir(parents=True, exist_ok=True)
        Image.fromarray(crop).save(OUT / file, quality=95)
        rows.append({'file': file, 'image_id': image_id, 'label': b.label, 'ox': b.x, 'oy': b.y, 'ow': b.w, 'oh': b.h,
                     'x0': left, 'y0': top, 'side': side, 'img_w': W, 'img_h': H, 'med_car_area': median_car_area})

crops = pd.DataFrame(rows)
crops.to_csv(OUT / 'crops.csv', index=False)

image_ids = sorted(crops.image_id.unique())
_, val_ids = train_test_split(image_ids, test_size=0.10, random_state=42)
split = ['val' if i in set(val_ids) else 'train' for i in image_ids]
pd.DataFrame({'image_id': image_ids, 'split': split}).to_csv(OUT / 'splits.csv', index=False)

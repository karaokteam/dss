"""Train a YOLO26 detector.   python scripts/02_train_yolo.py y26l_1920 full   (or split)

full  = all labelled images, 27 epochs, last.pt is used on the test set
split = 70% of the images, up to 30 epochs, best.pt is used on split_val
"""
import sys
from pathlib import Path

from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import augment, paths, small_shm  # noqa: E402

MODELS = {                      # weights, image size, batch size
    'y26l_1536':     ('yolo26l.pt', 1536, 20),
    'y26l_1920':     ('yolo26l.pt', 1920, 12),
    'y26x_1920':     ('yolo26x.pt', 1920, 8),
    'y26l_1920_aug': ('yolo26l.pt', 1920, 12),
}

name, data = sys.argv[1], sys.argv[2]
weights, image_size, batch = MODELS[name]

settings = dict(epochs=27, patience=0, close_mosaic=0, hsv_h=0.015, hsv_v=0.4, scale=0.5)
dataset = paths.YOLO_FULL if data == 'full' else paths.YOLO_SPLIT
if data == 'split':
    settings.update(epochs=30, patience=10, close_mosaic=3)
if name == 'y26x_1920':
    settings.update(close_mosaic=3)
if name == 'y26l_1920_aug':
    augment.install()
    dataset = paths.RFS_FULL if data == 'full' else paths.RFS_SPLIT
    settings.update(patience=0, close_mosaic=0, hsv_h=0.02, hsv_v=0.5, scale=0.6)

if '--small-shm' in sys.argv:
    small_shm.install()

YOLO(weights).train(
    data=str(dataset / 'data.yaml'), imgsz=image_size, batch=batch, flipud=0.5, cos_lr=True,
    cache='ram', workers=48, seed=0, project=str(paths.RUNS), name=f'{data}_{name}', **settings,
)

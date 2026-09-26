"""Build a TensorRT engine from a YOLO checkpoint.   python export_engine.py fp16 [checkpoint.pt]

Dynamic batch 1-16 at 1920x1920. The one-to-many head is kept, so NMS runs afterwards, as in phase 1.
TensorRT 11 has no fp16 / int8 builder flags: Ultralytics first rewrites the ONNX graph with NVIDIA ModelOpt.
"""
import shutil
import sys
from pathlib import Path

from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'phase1_train'))
from roketsan import paths  # noqa: E402

precision = sys.argv[1]
checkpoint = Path(sys.argv[2]) if len(sys.argv) > 2 else paths.WEIGHTS / 'split' / 'yolo26l_1920_split.pt'

options = dict(format='engine', imgsz=1920, dynamic=True, batch=16)
if precision == 'fp16':
    options['half'] = True
if precision == 'int8':   # calibrated on split-train images; needs a lot of RAM at 1920 px (see README)
    calibration = paths.ROOT / 'engines' / 'calibration.yaml'
    calibration.parent.mkdir(parents=True, exist_ok=True)
    calibration.write_text(f'path: {paths.YOLO_SPLIT}\ntrain: images/train\nval: images/train\n'
                           'names: {0: car, 1: van, 2: truck, 3: bus}\n')
    options.update(int8=True, data=str(calibration), fraction=0.1)

engine = YOLO(checkpoint).export(**options)
target = paths.ROOT / 'engines' / f'{checkpoint.stem}_{precision}.engine'
target.parent.mkdir(parents=True, exist_ok=True)
shutil.move(engine, target)
print(target)

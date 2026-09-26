"""Train RF-DETR-L (rfdetr environment).   python scripts/03_train_rfdetr.py 1920 full   (or split)

full  -> runs/full_rfdetrL_<res>/last_ema.pth, split -> runs/split_rfdetrL_<res>/checkpoint_best_total.pth
"""
import sys
from pathlib import Path

from rfdetr import RFDETRLarge

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import paths, small_shm  # noqa: E402

resolution, data = int(sys.argv[1]), sys.argv[2]
if '--small-shm' in sys.argv:
    small_shm.install()

RFDETRLarge(resolution=resolution).train(
    dataset_dir=str(paths.COCO_FULL if data == 'full' else paths.COCO_SPLIT),
    output_dir=str(paths.RUNS / f'{data}_rfdetrL_{resolution}'),
    epochs=12, batch_size=16, grad_accum_steps=1, lr=1e-4, num_workers=24,
    early_stopping=(data == 'split'), early_stopping_patience=12,   # full: valid set is inside the training data
)

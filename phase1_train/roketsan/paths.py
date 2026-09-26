import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('ROKETSAN_ROOT', REPO / 'work'))
CONFIG = REPO / 'configs' / 'pipeline.yaml'

# Kaggle download
TRAIN_IMAGES = ROOT / 'data' / 'train' / 'images'
TRAIN_ANNOTATIONS = ROOT / 'data' / 'train' / 'annotations.csv'
TEST_IMAGES = ROOT / 'data' / 'test' / 'images'
SAMPLE_SUBMISSION = ROOT / 'data' / 'sample_submission.csv'

# Made by scripts/01_prepare_data.py
DATASETS = ROOT / 'datasets'
YOLO_FULL = DATASETS / 'yolo_full'      # all labelled images
YOLO_SPLIT = DATASETS / 'yolo_split'    # 70 / 15 / 15 split
COCO_FULL = DATASETS / 'coco_full'
COCO_SPLIT = DATASETS / 'coco_split'
RFS_FULL = DATASETS / 'rfs_full'        # class-balanced training lists
RFS_SPLIT = DATASETS / 'rfs_split'
BENCHMARKS = DATASETS / 'benchmarks'    # ground truth of split_val / split_test

RUNS = ROOT / 'runs'
WEIGHTS = ROOT / 'weights'
PREDICTIONS = ROOT / 'predictions'

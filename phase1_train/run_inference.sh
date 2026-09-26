#!/usr/bin/env bash
# Images -> final submission.   bash run_inference.sh            (test set)
#                                bash run_inference.sh /my/images (any folder)
# Needs the checkpoints in work/weights (see README). Set YOLO_PY / RFDETR_PY to the two environments' python.
set -e
cd "$(dirname "$0")"
PY=${YOLO_PY:-python}
IMAGES=${1:-test}

# fit the calibrator once, on split_val predictions of the split-trained models
if [ ! -f work/weights/calibrator.pkl ]; then
  $PY scripts/10_run_passes.py split_val
  $PY scripts/11_fuse_wbf.py split_val 0.0
  $PY scripts/12_calibrate.py fit
fi

$PY scripts/10_run_passes.py "$IMAGES"               # 22 passes
$PY scripts/11_fuse_wbf.py "$IMAGES"                 # stage 1 -> fused.csv
$PY scripts/12_calibrate.py apply "$IMAGES"          # stage 2 -> calibrated.csv
$PY scripts/13_rescore_carvan_dino.py "$IMAGES"      # stage 3 -> dino.csv
$PY scripts/14_rescore_truckbus_convnext.py "$IMAGES"   # stage 4 -> final_submission.csv

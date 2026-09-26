#!/usr/bin/env bash
# Train every model from the Kaggle data (one H200 per job; the jobs are independent).
# Add --small-shm to the train commands on machines with a tiny /dev/shm.
set -e
cd "$(dirname "$0")"
PY=${YOLO_PY:-python}
RF=${RFDETR_PY:-python}

$PY scripts/01_prepare_data.py

for model in y26l_1536 y26l_1920 y26x_1920 y26l_1920_aug; do
  $PY scripts/02_train_yolo.py $model full       # used on the test set
  $PY scripts/02_train_yolo.py $model split      # used on split_val (calibrator)
done
for resolution in 1536 1920; do
  $RF scripts/03_train_rfdetr.py $resolution full
  $RF scripts/03_train_rfdetr.py $resolution split
done

$PY scripts/04_train_convnext_classifier.py
$PY classifiers/dino_carvan/build_crops.py      # then train_cls.py, see classifiers/dino_carvan/README.md

# Finally copy the checkpoints to work/weights/ under the names in configs/pipeline.yaml.

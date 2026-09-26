# Phase 1: vehicle detection (karaokteam)

Detecting car, van, truck and bus in drone images for the Level Up AI | ROKETSAN hackathon.
Metric: mAP@0.5 over the four classes. Final submission: **public leaderboard 0.82093**.

## Pipeline

```
 image ──► 6 detectors, run 22 times (sizes, mirrors)
             │
   Stage 1   Weighted Boxes Fusion of the 22 passes ─────────────────► fused.csv
             │
   Stage 2   calibrator: re-ranks boxes by how many models agree ────► calibrated.csv
             │
   Stage 3   DINOv2 classifier re-scores car / van boxes ────────────► dino.csv
             │
   Stage 4   ConvNeXt classifier re-scores truck / bus boxes ────────► final_submission.csv
```

| | split_val mAP@0.5 | Public LB |
|---|---|---|
| Best single detector (YOLO26-X) | 84.01 | – |
| Stage 1 | 86.65 | – |
| Stages 1 + 3 | – | 0.81105 |
| Stages 1 + 2 + 3 | 86.98 | 0.81769 |
| **Stages 1–4 (final)** | | **0.82093** |

split_val is 15% of the labelled images, held out for all decisions (70 / 15 / 15 split).

## Models and passes

Two architectures (YOLO26 and RF-DETR), six trained detectors, all starting from COCO weights. Each is trained on
all labelled images for the test set, plus a "split twin" on 70% of them that is only used on split_val.

| # | Detector | Trained at | split_val alone | Passes | Why it is in the ensemble |
|---|---|---|---|---|---|
| 1 | YOLO26-L | 1536 px | 82.66 | 8 | the first strong model |
| 2 | YOLO26-L | 1920 px | 83.71 | 6 | higher resolution helps the small vehicles |
| 3 | YOLO26-X | 1920 px | 84.01 | 2 | larger model, best single detector |
| 4 | YOLO26-L, augmented | 1920 px | 83.54 | 2 | trained with blur / haze / colour / JPEG changes and more van-truck-bus images |
| 5 | RF-DETR-L | 1536 px | 82.60 | 2 | a different architecture (transformer) |
| 6 | RF-DETR-L | 1920 px | 83.28 | 2 | same, higher resolution |

A **pass** is one run of one detector over all images, at one input size, on the original image or a mirrored copy
(boxes are mirrored back). **Weight** is how much the pass counts in the fusion.

| Pass | Detector | Input size | Image | Weight |
|---|---|---|---|---|
| 1 | 1 · YOLO26-L 1536 | 1536 | original | 1 |
| 2 | 1 · YOLO26-L 1536 | 1536 | mirrored left-right | 1 |
| 3 | 1 · YOLO26-L 1536 | 1920 | original | 1 |
| 4 | 1 · YOLO26-L 1536 | 1920 | mirrored left-right | 1 |
| 5 | 1 · YOLO26-L 1536 | 2304 | original | 1 |
| 6 | 1 · YOLO26-L 1536 | 2304 | mirrored left-right | 1 |
| 7 | 2 · YOLO26-L 1920 | 1920 | original | 2 |
| 8 | 2 · YOLO26-L 1920 | 1920 | mirrored left-right | 2 |
| 9 | 5 · RF-DETR-L 1536 | 1536 | original | 1 |
| 10 | 5 · RF-DETR-L 1536 | 1536 | mirrored left-right | 1 |
| 11 | 6 · RF-DETR-L 1920 | 1920 | original | 1 |
| 12 | 6 · RF-DETR-L 1920 | 1920 | mirrored left-right | 1 |
| 13 | 1 · YOLO26-L 1536 | 1536 | upside down | 1 |
| 14 | 2 · YOLO26-L 1920 | 1920 | upside down | 2 |
| 15 | 1 · YOLO26-L 1536 | 1536 | rotated 180° | 1 |
| 16 | 2 · YOLO26-L 1920 | 1920 | rotated 180° | 2 |
| 17 | 2 · YOLO26-L 1920 | 2304 | original | 2 |
| 18 | 2 · YOLO26-L 1920 | 2304 | mirrored left-right | 2 |
| 19 | 3 · YOLO26-X 1920 | 1920 | original | 2 |
| 20 | 3 · YOLO26-X 1920 | 1920 | mirrored left-right | 2 |
| 21 | 4 · YOLO26-L 1920 augmented | 1920 | original | 2 |
| 22 | 4 · YOLO26-L 1920 augmented | 1920 | mirrored left-right | 2 |

The same list is in `configs/pipeline.yaml`. The numbering is the order the passes were added during the competition.

## Files

```
configs/pipeline.yaml    models, passes and all settings
roketsan/                shared code (paths, CSV format, metric, crops, augmentation)
scripts/01-04            data preparation and training
scripts/10-14            inference: passes, stages 1-4
scripts/15               format check before uploading
classifiers/dino_carvan  the car/van classifier (stage 3), by a teammate
run_training.sh          trains everything
run_inference.sh         images -> final_submission.csv
```

## How to run

Two Python 3.11 environments: `requirements/yolo.txt` and `requirements/rfdetr.txt`. Put the Kaggle data in
`work/data/` and run `python scripts/01_prepare_data.py`.

With the released weights:

```bash
bash tools/install_from_release.sh ~/Downloads
YOLO_PY=/path/to/yolo/python RFDETR_PY=/path/to/rfdetr/python bash run_inference.sh
```

From scratch: `bash run_training.sh`, copy the checkpoints to `work/weights/` (names in `configs/pipeline.yaml`),
then `run_inference.sh`. For new images: `bash run_inference.sh /path/to/images`.

## Notes

* Stage 1 reproduces the submitted fusion exactly (`fused.csv` md5 `79ad54a28a7c9b74b6f7962b8e47fc85`).
* The submitted calibrator (stage 2) was not seeded, so a refit gives slightly different scores; this code fixes
  the seed. The submitted final file has md5 `45c931b0b830e20f71ce8490e4946e48`.
* Only the competition's training data was used, with general pretrained weights (COCO, ImageNet, DINOv2).
  Licences: Ultralytics AGPL-3.0, rfdetr / timm Apache-2.0, ensemble-boxes MIT, scikit-learn BSD-3-Clause.

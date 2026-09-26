# karaokteam: Level Up AI | ROKETSAN Yapay Zekâ Hackathonu

Detecting **car, van, truck and bus** in drone images. Metric: mAP@0.5 over the four classes (vehicles under
200 px² are unlabelled and ignored). Final submission: **public leaderboard 0.82093**.

## The pipeline in one picture

```
 test image ──► 6 trained detectors, run 22 times (sizes, mirrors) ── see "Models and passes"
                    │
                    ▼
   Stage 1  Weighted Boxes Fusion, per class ─────────────────────► fused.csv
                    │
                    ▼
   Stage 2  learned support calibrator (gradient boosting, TP/FP) ─► calibrated.csv
                    │         "is this box backed by several model families?"
                    ▼
   Stage 3  DINOv2 ViT-L crop classifier: car vs van ─────────────► dino.csv
                    │
                    ▼
   Stage 4  ConvNeXt-L crop classifier: truck / bus ───────────────► final_submission.csv
```

| Step | split_val mAP@0.5 | Public LB |
|---|---|---|
| Best single detector (YOLO26-X 1920) | 84.01 | – |
| Stage 1: 22-pass fusion | 86.65 | not submitted alone |
| + stage 3 only | – (classifier saw split_val) | 0.81105 |
| + stage 2 + stage 3 | 86.98 (stage 2, out-of-fold) | 0.81769 |
| **+ stage 4 (final)** | +0.14 (stage 4 on the plain fusion) | **0.82093** |

Earlier milestones: YOLO + RF-DETR fusion 0.78710, 10-pass TTA 0.79972, 12-pass TTA 0.80731.

## Models and passes

Two architectures (YOLO26 and RF-DETR), **six trained detectors**. All start from COCO-pretrained weights and are
trained on all 6,471 labelled images for the test set. Each also has a "split twin" trained on 70% of the images;
the twins are only used on split_val (to make decisions and to fit the calibrator).

| # | Detector | Trained at | split_val alone (twin) | Passes | Why it is in the ensemble |
|---|---|---|---|---|---|
| 1 | YOLO26-L | 1536 px | 82.66 | 8 | the first strong model |
| 2 | YOLO26-L | 1920 px | 83.71 | 6 | higher resolution helps the small vehicles (+1.05 alone) |
| 3 | YOLO26-X | 1920 px | 84.01 | 2 | larger model, best single detector (+0.20 in the ensemble) |
| 4 | YOLO26-L, augmented | 1920 px | 83.54 | 2 | blur / haze / colour / JPEG augmentation and more van-truck-bus images (+0.10 in the ensemble) |
| 5 | RF-DETR-L | 1536 px | 82.60 | 2 | a different architecture (transformer); removing both RF-DETRs costs −0.44 |
| 6 | RF-DETR-L | 1920 px | 83.28 | 2 | same, higher resolution |

A **pass** is one run of one detector over all images: at one input size, on the original image or on a mirrored
copy (boxes found on a mirrored image are mirrored back). The 22 passes are the six detectors run in different ways
(test-time augmentation), not 22 models. **Weight** is how much the pass counts in the fusion: the three strongest
YOLO models (2, 3, 4) count double.

| Pass | Detector | Input size | Image the detector sees | Weight |
|---|---|---|---|---|
| 1 | 1 · YOLO26-L 1536 | 1536 | original | 1 |
| 2 | 1 · YOLO26-L 1536 | 1536 | mirrored left-right | 1 |
| 3 | 1 · YOLO26-L 1536 | 1920 (enlarged) | original | 1 |
| 4 | 1 · YOLO26-L 1536 | 1920 (enlarged) | mirrored left-right | 1 |
| 5 | 1 · YOLO26-L 1536 | 2304 (enlarged) | original | 1 |
| 6 | 1 · YOLO26-L 1536 | 2304 (enlarged) | mirrored left-right | 1 |
| 7 | 2 · YOLO26-L 1920 | 1920 | original | 2 |
| 8 | 2 · YOLO26-L 1920 | 1920 | mirrored left-right | 2 |
| 9 | 5 · RF-DETR-L 1536 | 1536 | original | 1 |
| 10 | 5 · RF-DETR-L 1536 | 1536 | mirrored left-right | 1 |
| 11 | 6 · RF-DETR-L 1920 | 1920 | original | 1 |
| 12 | 6 · RF-DETR-L 1920 | 1920 | mirrored left-right | 1 |
| 13 | 1 · YOLO26-L 1536 | 1536 | upside down | 1 |
| 14 | 2 · YOLO26-L 1920 | 1920 | upside down | 2 |
| 15 | 1 · YOLO26-L 1536 | 1536 | upside down and left-right (rotated 180°) | 1 |
| 16 | 2 · YOLO26-L 1920 | 1920 | upside down and left-right (rotated 180°) | 2 |
| 17 | 2 · YOLO26-L 1920 | 2304 (enlarged) | original | 2 |
| 18 | 2 · YOLO26-L 1920 | 2304 (enlarged) | mirrored left-right | 2 |
| 19 | 3 · YOLO26-X 1920 | 1920 | original | 2 |
| 20 | 3 · YOLO26-X 1920 | 1920 | mirrored left-right | 2 |
| 21 | 4 · YOLO26-L 1920 augmented | 1920 | original | 2 |
| 22 | 4 · YOLO26-L 1920 augmented | 1920 | mirrored left-right | 2 |

The numbering is the order in which the passes were added during the competition; it is kept because the fused
file is reproduced byte-for-byte in this order. Enlarged inputs make small vehicles bigger for the detector; the
upside-down passes work because all YOLO models were trained with vertical flips (a drone view has no "up").
The same table is in `configs/pipeline.yaml` (`hflip` = mirrored left-right, `vflip` = upside down).

## Repository layout

```
configs/pipeline.yaml        the whole inference recipe: models, the 22 passes, WBF / calibrator / classifier settings
roketsan/                    shared code
  paths.py                     every file location (one working folder, $ROKETSAN_ROOT, default ./work)
  submission.py                read / write the Kaggle CSV format
  metric.py                    local copy of the competition metric (python -m roketsan.metric file.csv)
  imagesets.py                 "test", "split_val" or any folder of images
  augment.py                   location-robustness photometric augmentation (augmented YOLO model)
  crops.py                     the crop rules of the two classifiers
  boxes.py, config.py, small_shm.py
scripts/
  01_prepare_data.py           70/15/15 split, YOLO + COCO datasets, class-balanced lists, split_val ground truth
  02_train_yolo.py             4 YOLO26 presets × {full data, split twin}
  03_train_rfdetr.py           RF-DETR-L 1536 / 1920 × {full, split}
  04_train_convnext_classifier.py
  10_run_passes.py             the 22 inference passes (predict_yolo_pass.py / predict_rfdetr_pass.py)
  11_fuse_wbf.py               stage 1
  12_calibrate.py              stage 2 (fit on split_val, apply to test)
  13_rescore_carvan_dino.py    stage 3
  14_rescore_truckbus_convnext.py  stage 4
  15_check_submission.py       format check before uploading
classifiers/dino_carvan/     teammate's car/van classifier: training script, crop builder, write-up
tools/install_from_release.sh  put the released weights and saved passes in place (no retraining needed)
run_training.sh, run_inference.sh
```

## Reproducing the submission

**Environments** (Python 3.11): `requirements/yolo.txt` for everything except RF-DETR, `requirements/rfdetr.txt`
for RF-DETR. We used one NVIDIA H200 (141 GB) per job.

**Data**: put the Kaggle download in `work/data/` (`train/images`, `train/annotations.csv`, `test/images`,
`sample_submission.csv`), then `python scripts/01_prepare_data.py`.

**A. From the released checkpoints** (about 1 hour, mostly the 22 passes; or minutes with the saved passes):

```bash
bash tools/install_from_release.sh ~/Downloads          # weights + saved test/split_val passes -> work/
YOLO_PY=/path/to/yolo/python RFDETR_PY=/path/to/rfdetr/python bash run_inference.sh
```

`run_inference.sh` skips passes that already exist, so with the saved passes it only fuses, calibrates and
re-scores. Checks: `work/predictions/test/fused.csv` must have md5 `79ad54a28a7c9b74b6f7962b8e47fc85` (stage 1 is
bit-exact); the submitted final file has md5 `45c931b0b830e20f71ce8490e4946e48` (see "Reproducibility").

**B. From scratch**: `bash run_training.sh`, copy the checkpoints to `work/weights/` under the names in
`configs/pipeline.yaml`, then run A. The full-data YOLO models train for 27 epochs (80–130 min each at 1920 px),
RF-DETR for 12 epochs, the ConvNeXt classifier for 2 epochs (5 min).

**New images** (e.g. the stage-2 drone images): `bash run_inference.sh /path/to/images` writes
`work/predictions/<folder>/final_submission.csv` in the same format.

## How each part works

**Validation.** All labelled images were split 70/15/15 (seed 0). Every design decision was made on the 15%
`split_val` part with the competition metric; `split_test` was used once per decision as a check. The final models
were then retrained on 100% of the data ("full") with the same recipe; the 70% models ("split twins") are kept
because the calibrator is fitted on their split_val predictions. Local gains transferred to the leaderboard at
roughly 85%, except for extra TTA passes (below).

**Detectors** (`02`, `03`). The six detectors are listed under "Models and passes". They are trained at high
resolution because the vehicles are small (median ~40×40 px). Inference uses **multi-label NMS**: a box is kept under
every class above the threshold (+2.9 mAP, because mAP ranks each class separately).

**Stage 1 – fusion** (`10`, `11`). The 22 passes are fused with Weighted Boxes Fusion, which merges boxes of the
same class (IoU 0.7). The fused score is the weighted mean score times the share of (weighted) passes that found
the box.

**Stage 2 – calibrator** (`12`). WBF counts passes, so six TTA passes of one checkpoint count more than three
different model families agreeing. For every fused box we compute, per model family, its best matching score and the
share of its passes that support it, plus the competing class's score (car↔van, truck↔bus), size and aspect. A
per-class gradient-boosting classifier trained on split_val predicts whether the box is a true positive; the new
score is √(p · fused score). Out-of-fold on split_val: 86.65 → 86.98; on the leaderboard it was worth +0.66.

**Stage 3 – car/van classifier** (`13`, `classifiers/dino_carvan`). Car/van confusion was the largest error (van AP
~79). A DINOv2 ViT-L classifier looks at a square crop of twice the vehicle's size (context shows relative size):
new score = s^0.6 · q^0.4, q = the classifier's probability of the box's label.

**Stage 4 – truck/bus classifier** (`04`, `14`). A ConvNeXt-L classifier (ImageNet-22k weights, 4 classes, trained
on the 70% split only) re-scores truck and bus boxes: s^0.8 · p^0.2 (+0.14 on split_val, +0.32 on the leaderboard).

## What did not help

| Idea | split_val effect |
|---|---|
| Tiled inference (SAHI) | +0.02 |
| More TTA (vertical flips, 2304 px; 12 → 18 passes) | +0.19 locally but −0.20 on the leaderboard: kept only inside the 22-pass set |
| Two-stage fusion, rank calibration, other WBF settings | −1.9 to +0.04 |
| Confidence thresholds / cut-offs after fusion | only lose (AP is a ranking metric) |
| Loss re-weighting towards mAP@0.5 | −0.6 |
| Weight averaging of the last epochs (model soup) | −0.02 |
| Box scaling, car↔van soft suppression | ≤ +0.08 |
| Calibrator variants (more features, ensembles, per-class blends) | within ±0.05 |

## Reproducibility

* Stage 1 is bit-exact from the saved passes (verified: 200/200 images identical to the competition code, and the
  fused test file has the submitted md5). Re-running the passes on other hardware changes scores in the last digits.
* Stage 2: the submitted run used sklearn's default early stopping with an unseeded internal split, so refits varied
  by about ±0.1 out-of-fold. This code fixes `random_state` and saves the fitted models (`work/weights/calibrator.pkl`),
  so its runs are repeatable, but they will not match the submitted stage-2 file bit for bit. The features are
  identical to the competition code (verified on 115,364 split_val boxes).
* Stage 3 maths reproduces the submitted file exactly from the saved classifier probabilities (2,118/2,118 rows).
* Stage 4 classifies only truck/bus boxes (the competition run classified all boxes and used the truck/bus ones);
  the maths is the same, bf16 GPU numerics may differ in the last digits.
* The class-balanced list of the full-data set was built from two folders during the competition (old 90/10 split);
  here it is built from one folder, so the shuffled list differs (same statistics).
* `classifiers/dino_carvan/build_crops.py` re-implements a step that ran in a Colab notebook.

## Rules and licences

No external data or labels: only the competition's training images, plus general pretrained weights — COCO
(Ultralytics YOLO26, AGPL-3.0; RF-DETR, Apache-2.0) and ImageNet / self-supervised (ConvNeXt via timm, DINOv2 —
both released under permissive licences). Libraries: Ultralytics (AGPL-3.0), rfdetr (Apache-2.0), timm
(Apache-2.0), ensemble-boxes (MIT), scikit-learn (BSD-3-Clause), PyTorch (BSD-style).

# DINOv2 car/van crop classifier (stage 3)

Built by a teammate to separate the detectors' most-confused pair, car and van. The full Turkish write-up with every
experiment is in [README_tr.md](README_tr.md); `train_cls.py` is the training script, unchanged.

| | |
|---|---|
| Model | `vit_large_patch14_dinov2.lvd142m` (timm, DINOv2 weights, Apache-2.0), 224 px input, linear head, 2 classes |
| Crops | square of side 2 x the box's long side, centred, grey outside the image (context shows relative size) |
| Data | car/van ground-truth boxes of the competition training images only; image-level 10% validation split |
| Training | 15 epochs, batch 64, AdamW lr 2e-4, layer-wise lr decay 0.85, 2 warm-up epochs, drop path 0.2, weight decay 0.05, gradient clipping 1.0, EMA 0.9995, label smoothing 0.1, balanced sampling (every van once + 2x as many cars per epoch), 90-degree rotations/flips, random down-scaling, bf16; ~5 min/epoch on an A100 |
| Validation (8-way TTA) | top-1 0.934, van recall 0.80, van precision 0.78, van F1 0.789 |
| Weights | `Dino-Vit_best.pt` (1.2 GB) -> copy to `work/weights/dino_carvan_vitl.pt` |

```bash
python classifiers/dino_carvan/build_crops.py        # -> work/datasets/dino_crops
python classifiers/dino_carvan/train_cls.py \
    --data work/datasets/dino_crops --split_csv work/datasets/dino_crops/splits.csv --out work/runs/dino_carvan \
    --model vit_large_patch14_dinov2.lvd142m --imgsz 224 --epochs 15 --batch 64 --lr 2e-4 \
    --layer_decay 0.85 --warmup_epochs 2 --drop_path 0.2 --clip_grad 1.0 --ema 0.9995
```

`build_crops.py` re-implements the crop step from the README (it originally ran in a Colab notebook), so the
validation split may not match the original run image for image. The classifier's training images overlap our
split_val, so it could only be judged on the public leaderboard: the fusion + this re-scoring scored 0.81105 (the
fusion alone was not submitted; our previous best was 0.80731), and 0.81769 on top of the calibrator.

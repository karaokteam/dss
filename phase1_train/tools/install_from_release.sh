#!/usr/bin/env bash
# Put the released checkpoints and saved predictions where the pipeline expects them, so the final submission can be
# rebuilt without retraining.
#
#   bash tools/install_from_release.sh <folder with the release zips>
#
# Expected in that folder: roketsan_final_v5.zip, roketsan_final_v5_classifiers.zip,
# roketsan_split_twin_weights.zip, carVanDino.zip
set -euo pipefail
REL=${1:?folder with the release zips}
W=${ROKETSAN_ROOT:-$(dirname "$0")/../work}/weights
P=${ROKETSAN_ROOT:-$(dirname "$0")/../work}/predictions
mkdir -p "$W/split" "$P/test/passes" "$P/split_val/passes"

# full-data detectors (names already match configs/pipeline.yaml)
unzip -o -j "$REL/roketsan_final_v5.zip" 'final_v5/weights/*' -d "$W"
# split twins
Z="$REL/roketsan_split_twin_weights.zip"; S=roketsan_split_twin_weights
unzip -p "$Z" $S/runs/split_y26l_1536/weights/best.pt            > "$W/split/yolo26l_1536_split.pt"
unzip -p "$Z" $S/runs/split_y26l_1920/weights/best.pt            > "$W/split/yolo26l_1920_split.pt"
unzip -p "$Z" $S/runs/split_y26x_1920/weights/best.pt            > "$W/split/yolo26x_1920_split.pt"
unzip -p "$Z" $S/runs/split_y26l1920_aug/weights/best.pt         > "$W/split/yolo26l_1920_aug_split.pt"
unzip -p "$Z" $S/runs_rfdetr/split_rfdetrL_1536_b16/checkpoint_best_total.pth > "$W/split/rfdetrL_1536_split.pth"
unzip -p "$Z" $S/runs_rfdetr/split_rfdetrL_1920/checkpoint_best_total.pth     > "$W/split/rfdetrL_1920_split.pth"
# second-stage classifiers
unzip -p "$REL/roketsan_final_v5_classifiers.zip" final_v5_classifiers/convnextL_cls4_split.pt > "$W/convnextL_cls4_split.pt"
unzip -p "$REL/carVanDino.zip" carVanDino/Dino-Vit_best.pt > "$W/dino_carvan_vitl.pt"

# saved inference passes (skip the GPU part of stage 1) and the split_val material for the calibrator
TMP=$(mktemp -d)
unzip -q -o "$REL/roketsan_final_v5.zip" 'final_v5/test_passes/*' 'final_v5/val_passes/*' -d "$TMP"
for f in "$TMP"/final_v5/test_passes/*.csv; do n=$(basename "$f" | cut -c1-2); cp "$f" "$P/test/passes/$n.csv"; done
for f in "$TMP"/final_v5/val_passes/[0-9][0-9]_*.csv; do n=$(basename "$f" | cut -c1-2); cp "$f" "$P/split_val/passes/$n.csv"; done
cp "$TMP/final_v5/val_passes/wbf_tmp_skip0.0.csv" "$P/split_val/fused.csv"
rm -rf "$TMP"
ls -la "$W" "$W/split"
echo "installed; now run scripts/01_prepare_data.py (benchmarks) and run_inference.sh, or the single stages"

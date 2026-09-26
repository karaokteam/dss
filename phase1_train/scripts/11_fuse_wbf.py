"""Stage 1: fuse the 22 passes with Weighted Boxes Fusion.   python scripts/11_fuse_wbf.py test

Boxes are only merged within a class, so a vehicle can keep both a "car" and a "van" box.
Writes predictions/<set>/fused.csv. For split_val we used skip 0.0: python scripts/11_fuse_wbf.py split_val 0.0
"""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from ensemble_boxes import weighted_boxes_fusion
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import CLASSES, config, imagesets, submission  # noqa: E402

CFG = config.load()
WEIGHTS = [p['weight'] for p in CFG['passes']]


def fuse(width, height, pass_texts, skip):
    size = [width, height, width, height]
    all_boxes, all_scores, all_labels = [], [], []
    for text in pass_texts:
        labels, scores, boxes = submission.parse(text)
        corners = np.c_[boxes[:, :2], boxes[:, :2] + boxes[:, 2:]] / size   # x1 y1 x2 y2, 0..1
        all_boxes.append(np.clip(corners, 0, 1).tolist())
        all_scores.append(scores.tolist())
        all_labels.append([CLASSES.index(label) for label in labels])

    if not any(all_scores):
        return 'none'
    boxes, scores, labels = weighted_boxes_fusion(all_boxes, all_scores, all_labels, weights=WEIGHTS,
                                                  iou_thr=CFG['wbf']['iou'], skip_box_thr=skip,
                                                  conf_type=CFG['wbf']['conf_type'])
    parts = []
    for (x1, y1, x2, y2), score, label in zip(boxes * size, scores, labels):
        parts.append(f'{CLASSES[int(label)]} {score:.4f} {round(x1)} {round(y1)} {round(x2 - x1)} {round(y2 - y1)}')
    return ' '.join(parts) or 'none'


if __name__ == '__main__':
    images = sys.argv[1]
    skip = float(sys.argv[2]) if len(sys.argv) > 2 else CFG['wbf']['skip_box_thr']
    folder = imagesets.output_dir(images)
    ids, files = imagesets.load(images)
    passes = [submission.read(folder / 'passes' / f'{p["id"]:02d}.csv') for p in CFG['passes']]

    jobs = [(*Image.open(files[i]).size, [p[i] for p in passes], skip) for i in ids]
    with Pool(32) as pool:
        fused = pool.starmap(fuse, jobs, chunksize=8)
    submission.write(folder / 'fused.csv', dict(zip(ids, fused)))

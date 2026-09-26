"""Competition metric: mean AP@0.5 over car, van, truck, bus (COCO 101-point AP).

Vehicles under 200 px² are not labelled, so detections matched to them and unmatched detections
under 200 px² are ignored.   Usage: python -m roketsan.metric predictions.csv
"""
import json
import sys

import numpy as np

from . import CLASSES, paths, submission
from .boxes import iou

MIN_AREA = 200


def load_benchmark(name):
    return json.loads((paths.BENCHMARKS / f'{name}.json').read_text())


def average_precision(images):
    """images: list of (ground-truth boxes, detected boxes, detection scores) for one class."""
    all_scores, all_tp = [], []
    n_gt = 0
    for gt, det, scores in images:
        gt_small = gt[:, 2] * gt[:, 3] < MIN_AREA
        n_gt += int((~gt_small).sum())

        order = np.argsort(-scores, kind='mergesort')
        det, scores = det[order], scores[order]
        tp = np.zeros(len(scores), bool)
        ignore = np.zeros(len(scores), bool)
        overlaps = iou(det, gt)
        used = np.zeros(len(gt), bool)
        for i in range(len(scores)):
            candidates = ~used & (overlaps[i] >= 0.5)
            if not candidates.any():
                continue
            if (candidates & ~gt_small).any():      # prefer a vehicle that counts
                candidates &= ~gt_small
            match = np.argmax(np.where(candidates, overlaps[i], -1.0))
            used[match] = True
            tp[i] = not gt_small[match]
            ignore[i] = gt_small[match]
        ignore |= ~tp & (det[:, 2] * det[:, 3] < MIN_AREA)

        all_scores.append(scores[~ignore])
        all_tp.append(tp[~ignore])

    if n_gt == 0:
        return None
    scores = np.concatenate(all_scores)
    tp = np.concatenate(all_tp)[np.argsort(-scores, kind='mergesort')]
    if len(tp) == 0:
        return 0.0
    recall = np.cumsum(tp) / n_gt
    precision = np.cumsum(tp) / np.arange(1, len(tp) + 1)
    precision = np.maximum.accumulate(precision[::-1])[::-1]
    idx = np.searchsorted(recall, np.linspace(0, 1, 101), side='left')
    return float(np.where(idx < len(precision), precision[np.minimum(idx, len(precision) - 1)], 0).mean())


def score(benchmark, predictions):
    """predictions: {image_id: PredictionString}. Returns mAP and per-class AP."""
    per_class = {name: [] for name in CLASSES}
    for image_id in sorted(benchmark['images']):
        gt = np.array(benchmark['images'][image_id]['g'], dtype=float).reshape(-1, 5)
        labels, scores, boxes = submission.parse(predictions[image_id])
        valid = (boxes[:, 2] > 0) & (boxes[:, 3] > 0)
        for c, name in enumerate(CLASSES):
            mine = valid & (labels == name)
            per_class[name].append((gt[gt[:, 0] == c, 1:], boxes[mine], scores[mine]))
    ap = {name: average_precision(images) for name, images in per_class.items()}
    return np.mean([v for v in ap.values() if v is not None]), ap


def score_file(path, benchmark='split_val'):
    return score(load_benchmark(benchmark), submission.read(path))[0]


if __name__ == '__main__':
    mean_ap, ap = score(load_benchmark('split_val'), submission.read(sys.argv[1]))
    for name, v in ap.items():
        print(f'{name:6s} {100 * v:.2f}')
    print(f'mAP@0.5 {100 * mean_ap:.2f}')

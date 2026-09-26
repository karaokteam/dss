"""Stage 2: re-rank fused boxes by how the six model families support them.

    python scripts/12_calibrate.py fit          learn on split_val (prints the out-of-fold mAP)
    python scripts/12_calibrate.py apply test   fused.csv -> calibrated.csv

WBF counts passes, so six flips of one model weigh more than three different models agreeing. A small
gradient-boosting model per class learns from split_val which boxes are real; new score = sqrt(p * fused score).
"""
import pickle
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import CLASSES, config, imagesets, metric, paths, submission  # noqa: E402

CFG = config.load()
SETTINGS = CFG['calibrator']
FAMILIES = config.families(CFG)
FAMILY_OF_PASS = [FAMILIES.index(p['model']) for p in CFG['passes']]
FAMILY_SIZE = np.bincount(FAMILY_OF_PASS)
COMPETITOR = {'car': 'van', 'van': 'car', 'truck': 'bus', 'bus': 'truck'}
MODEL_FILE = paths.WEIGHTS / 'calibrator.pkl'


def iou(a, b):
    # Same formula as in the submitted run: with integer boxes some pairs are exactly on the 0.55 threshold,
    # and the +1e-9 decides them.
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 0] + a[:, None, 2], b[None, :, 0] + b[None, :, 2])
    y2 = np.minimum(a[:, None, 1] + a[:, None, 3], b[None, :, 1] + b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    return inter / (a[:, 2, None] * a[:, 3, None] + (b[:, 2] * b[:, 3])[None] - inter + 1e-9)


def best_support(boxes, other_boxes, other_scores):
    """For each box: the highest score among other boxes that overlap it enough (0 if none)."""
    overlapping = iou(boxes, other_boxes) >= SETTINGS['support_iou']
    return np.where(overlapping, other_scores[None], 0).max(1)


def features(fused_text, pass_texts):
    labels, scores, boxes = submission.parse(fused_text)
    family_best = np.zeros((len(scores), len(FAMILIES)))   # best supporting score per family
    family_hits = np.zeros((len(scores), len(FAMILIES)))   # how many passes of the family support the box
    competitor = np.zeros(len(scores))                      # best score of the confusable class at the same place

    for pass_no, text in enumerate(pass_texts):
        family = FAMILY_OF_PASS[pass_no]
        p_labels, p_scores, p_boxes = submission.parse(text)
        for cls in CLASSES:
            mine = labels == cls
            same = p_labels == cls
            other = p_labels == COMPETITOR[cls]
            if mine.any() and same.any():
                best = best_support(boxes[mine], p_boxes[same], p_scores[same])
                family_best[mine, family] = np.maximum(family_best[mine, family], best)
                family_hits[mine, family] += best > 0
            if mine.any() and other.any():
                best = best_support(boxes[mine], p_boxes[other], p_scores[other])
                competitor[mine] = np.maximum(competitor[mine], best)

    area = boxes[:, 2] * boxes[:, 3]
    aspect = np.maximum(boxes[:, 2], 1) / np.maximum(boxes[:, 3], 1)
    return np.column_stack([scores, family_best, family_hits / FAMILY_SIZE, (family_best > 0).sum(1), competitor,
                            np.log(np.maximum(area, 1)), np.log(aspect)])


def true_positives(fused_text, ground_truth):
    """1 for boxes that match a ground-truth vehicle of the same class (IoU >= 0.5, highest score first)."""
    labels, scores, boxes = submission.parse(fused_text)
    gt = np.array(ground_truth, dtype=float).reshape(-1, 5)
    is_tp = np.zeros(len(scores))
    for c, cls in enumerate(CLASSES):
        mine = np.where(labels == cls)[0]
        mine = mine[np.argsort(-scores[mine])]
        gt_boxes = gt[gt[:, 0] == c, 1:]
        overlaps = iou(boxes[mine], gt_boxes)
        used = np.zeros(len(gt_boxes), bool)
        for row, box in enumerate(mine):
            candidates = np.where((overlaps[row] >= 0.5) & ~used)[0]
            if len(candidates):
                used[candidates[np.argmax(overlaps[row, candidates])]] = True
                is_tp[box] = 1
    return is_tp


def load(images):
    folder = imagesets.output_dir(images)
    ids, _ = imagesets.load(images)
    fused = submission.read(folder / 'fused.csv')
    passes = [submission.read(folder / 'passes' / f'{p["id"]:02d}.csv') for p in CFG['passes']]
    with Pool(32) as pool:
        X = pool.starmap(features, [(fused[i], [p[i] for p in passes]) for i in ids], chunksize=4)
    return ids, fused, X


def new_model():
    return HistGradientBoostingClassifier(**SETTINGS['gbm'], random_state=SETTINGS['random_state'])


def blend(p, fused_score):
    b = SETTINGS['blend']
    return np.clip(p, 1e-6, 1) ** b * np.clip(fused_score, 1e-6, 1) ** (1 - b)


def write(path, ids, fused, new_scores):
    rows = {}
    for image_id, scores in zip(ids, new_scores):
        labels, _, boxes = submission.parse(fused[image_id])
        rows[image_id] = submission.to_text(labels, scores, boxes)
    submission.write(path, rows)


def fit():
    ids, fused, X_per_image = load('split_val')
    ground_truth = metric.load_benchmark('split_val')['images']
    X = np.concatenate(X_per_image)
    y = np.concatenate([true_positives(fused[i], ground_truth[i]['g']) for i in ids])
    labels = np.concatenate([submission.parse(fused[i])[0] for i in ids])
    image_no = np.concatenate([[k] * len(x) for k, x in enumerate(X_per_image)])

    # out-of-fold check: every box is scored by a model that did not see its image
    p = np.zeros(len(y))
    for cls in CLASSES:
        rows = np.where(labels == cls)[0]
        for train, test in GroupKFold(SETTINGS['folds']).split(rows, groups=image_no[rows]):
            model = new_model().fit(X[rows[train]], y[rows[train]])
            p[rows[test]] = model.predict_proba(X[rows[test]])[:, 1]
    split_at = np.cumsum([len(x) for x in X_per_image])[:-1]
    out_of_fold = imagesets.output_dir('split_val') / 'calibrated_oof.csv'
    write(out_of_fold, ids, fused, np.split(blend(p, X[:, 0]), split_at))
    before = metric.score_file(imagesets.output_dir('split_val') / 'fused.csv')
    after = metric.score_file(out_of_fold)
    print(f'split_val mAP@0.5: fused {100 * before:.2f} -> calibrated (out-of-fold) {100 * after:.2f}')

    models = {cls: new_model().fit(X[labels == cls], y[labels == cls]) for cls in CLASSES}
    MODEL_FILE.write_bytes(pickle.dumps(models))


def apply(images):
    models = pickle.loads(MODEL_FILE.read_bytes())
    ids, fused, X_per_image = load(images)
    new_scores = []
    for image_id, X in zip(ids, X_per_image):
        labels = submission.parse(fused[image_id])[0]
        p = np.zeros(len(labels))
        for cls in CLASSES:
            if (labels == cls).any():
                p[labels == cls] = models[cls].predict_proba(X[labels == cls])[:, 1]
        new_scores.append(blend(p, X[:, 0]))
    write(imagesets.output_dir(images) / 'calibrated.csv', ids, fused, new_scores)


if __name__ == '__main__':
    if sys.argv[1] == 'fit':
        fit()
    else:
        apply(sys.argv[2])

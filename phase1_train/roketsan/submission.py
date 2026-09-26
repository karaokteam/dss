"""Kaggle format: image_id,PredictionString with "label conf x y w h ..." per image, or "none"."""
import numpy as np
import pandas as pd


def parse(text):
    """Returns labels, scores, boxes (x, y, w, h)."""
    if text == 'none':
        return np.array([], dtype=object), np.zeros(0), np.zeros((0, 4))
    t = text.split()
    labels = np.array(t[0::6], dtype=object)
    scores = np.array(t[1::6], dtype=float)
    boxes = np.array([t[i + 2:i + 6] for i in range(0, len(t), 6)], dtype=float)
    return labels, scores, boxes


def to_text(labels, scores, boxes):
    """Highest score first, 5 decimals, integer boxes."""
    if len(scores) == 0:
        return 'none'
    parts = []
    for i in np.argsort(-scores, kind='stable'):
        x, y, w, h = boxes[i]
        parts.append(f'{labels[i]} {scores[i]:.5f} {int(x)} {int(y)} {int(w)} {int(h)}')
    return ' '.join(parts)


def read(path):
    """{image_id: PredictionString}"""
    d = pd.read_csv(path, keep_default_na=False)
    return dict(zip(d.image_id.astype(str), d.PredictionString))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['image_id,PredictionString'] + [f'{image_id},{text}' for image_id, text in rows.items()]
    path.write_text('\n'.join(lines) + '\n')

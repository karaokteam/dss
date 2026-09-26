"""Check a submission before uploading.   python scripts/15_check_submission.py work/predictions/test/final_submission.csv"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import CLASSES, imagesets, submission  # noqa: E402

rows = submission.read(sys.argv[1])
ids, files = imagesets.load('test')

problems = []
if list(rows) != ids:
    problems.append('image ids are not the sample_submission ids in the same order')
for image_id, text in rows.items():
    width, height = Image.open(files[image_id]).size
    labels, scores, boxes = submission.parse(text)
    for label, score, (x, y, w, h) in zip(labels, scores, boxes):
        inside = x >= 0 and y >= 0 and x + w <= width + 1 and y + h <= height + 1
        if label not in CLASSES or not 0 <= score <= 1 or w <= 0 or h <= 0 or not inside:
            problems.append(f'{image_id}: {label} {score} {x} {y} {w} {h}')

print('\n'.join(problems[:20]) or 'format OK')

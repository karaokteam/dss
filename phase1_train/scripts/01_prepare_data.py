"""Build the YOLO / COCO datasets, the 70/15/15 split, class-balanced lists and split_val ground truth."""
import json
import math
import random
import sys
from pathlib import Path

import pandas as pd
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import CLASSES, paths  # noqa: E402

annotations = {}
for row in pd.read_csv(paths.TRAIN_ANNOTATIONS).itertuples():
    annotations.setdefault(row.image_id, []).append(row)


def read_boxes(image):
    """[(class, x, y, w, h)] of one training image, clipped to the image."""
    W, H = Image.open(image).size
    boxes = []
    for r in annotations.get(image.stem, []):
        x1, y1 = max(r.x, 0), max(r.y, 0)
        x2, y2 = min(r.x + r.w, W), min(r.y + r.h, H)
        if x2 > x1 and y2 > y1:
            boxes.append((CLASSES.index(r.label), x1, y1, x2 - x1, y2 - y1))
    return boxes, W, H


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        dst.symlink_to(src)


def write_yolo(root, part, images):
    """YOLO labels for one part; returns the ground truth in pixels."""
    (root / 'labels' / part).mkdir(parents=True, exist_ok=True)
    ground_truth = {}
    for image in images:
        link(image, root / 'images' / part / image.name)
        boxes, W, H = read_boxes(image)
        lines = [f'{c} {(x + w / 2) / W:.6f} {(y + h / 2) / H:.6f} {w / W:.6f} {h / H:.6f}' for c, x, y, w, h in boxes]
        (root / 'labels' / part / f'{image.stem}.txt').write_text('\n'.join(lines))
        ground_truth[image.stem] = {'g': [[c, round(x, 2), round(y, 2), round(w, 2), round(h, 2)] for c, x, y, w, h in boxes]}
    return ground_truth


def write_data_yaml(root, train, val):
    names = ''.join(f'  {i}: {c}\n' for i, c in enumerate(CLASSES))
    (root / 'data.yaml').write_text(f'path: {root}\ntrain: {train}\nval: {val}\nnames:\n{names}')


def write_coco(folder, images):
    coco_images, coco_boxes = [], []
    for image_id, image in enumerate(sorted(images), 1):
        link(image, folder / image.name)
        boxes, W, H = read_boxes(image)
        coco_images.append({'id': image_id, 'file_name': image.name, 'width': W, 'height': H})
        for c, x, y, w, h in boxes:
            coco_boxes.append({'id': len(coco_boxes) + 1, 'image_id': image_id, 'category_id': c + 1,
                               'bbox': [x, y, w, h], 'area': w * h, 'iscrowd': 0})
    categories = [{'id': i + 1, 'name': c, 'supercategory': 'vehicle'} for i, c in enumerate(CLASSES)]
    (folder / '_annotations.coco.json').write_text(
        json.dumps({'images': coco_images, 'annotations': coco_boxes, 'categories': categories}))


def write_class_balanced(out, image_folder):
    """Repeat-factor sampling: images with rare classes (van, truck, bus) appear more often; epoch grows ~1.25x."""
    images = sorted(image_folder.glob('*.jpg'))
    classes = []
    for image in images:
        label_file = Path(str(image).replace('/images/', '/labels/')).with_suffix('.txt')
        classes.append({int(line.split()[0]) for line in label_file.read_text().splitlines() if line})
    share = [sum(c in s for s in classes) / len(images) for c in range(len(CLASSES))]

    def repeats(t):
        return [max([1.0] + [math.sqrt(t / share[c]) for c in s]) for s in classes]

    best_t = min((t / 100 for t in range(5, 100)), key=lambda t: abs(sum(repeats(t)) / len(images) - 1.25))
    rng = random.Random(0)
    lines = []
    for image, r in zip(images, repeats(best_t)):
        n = int(r) + (rng.random() < r - int(r))
        lines += [str(image)] * n
    rng.shuffle(lines)

    out.mkdir(parents=True, exist_ok=True)
    (out / 'train.txt').write_text('\n'.join(lines) + '\n')
    write_data_yaml(out, out / 'train.txt', paths.YOLO_SPLIT / 'images' / 'val')


images = sorted(paths.TRAIN_IMAGES.glob('*.jpg'))

# 70 / 15 / 15 split, seed 0
shuffled = images[:]
random.Random(0).shuffle(shuffled)
n = round(len(images) * 0.15)
split = {'val': shuffled[:n], 'test': shuffled[n:2 * n], 'train': shuffled[2 * n:]}

paths.BENCHMARKS.mkdir(parents=True, exist_ok=True)
for part, part_images in split.items():
    ground_truth = write_yolo(paths.YOLO_SPLIT, part, part_images)
    if part != 'train':
        benchmark = {'image_dir': str(paths.YOLO_SPLIT / 'images' / part), 'images': ground_truth}
        (paths.BENCHMARKS / f'split_{part}.json').write_text(json.dumps(benchmark))
write_data_yaml(paths.YOLO_SPLIT, 'images/train', 'images/val')

# all labelled images (Ultralytics needs a val set; split_val is inside the training data here)
write_yolo(paths.YOLO_FULL, 'all', images)
write_data_yaml(paths.YOLO_FULL, 'images/all', paths.YOLO_SPLIT / 'images' / 'val')

# COCO format for RF-DETR
write_coco(paths.COCO_SPLIT / 'train', split['train'])
write_coco(paths.COCO_SPLIT / 'valid', split['val'])
write_coco(paths.COCO_SPLIT / 'test', split['test'])
write_coco(paths.COCO_FULL / 'train', images)
link(paths.COCO_SPLIT / 'valid', paths.COCO_FULL / 'valid')
link(paths.COCO_SPLIT / 'test', paths.COCO_FULL / 'test')

write_class_balanced(paths.RFS_SPLIT, paths.YOLO_SPLIT / 'images' / 'train')
write_class_balanced(paths.RFS_FULL, paths.YOLO_FULL / 'images' / 'all')

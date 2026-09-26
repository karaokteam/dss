"""Stage 3: re-score car/van boxes with the DINOv2 car-vs-van classifier.   python scripts/13_rescore_carvan_dino.py test

car: s^0.6 * (1 - p_van)^0.4, van: s^0.6 * p_van^0.4, for boxes with s >= 0.03 (lower ones get p_van = 0.5).
calibrated.csv -> dino.csv
"""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import timm
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import config, imagesets, paths, submission  # noqa: E402
from roketsan.crops import square_crop  # noqa: E402

CFG = config.load()['dino_carvan']


class CarVanClassifier(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = timm.create_model(CFG['backbone'], pretrained=False, num_classes=0, img_size=CFG['image_size'])
        self.head = torch.nn.Linear(self.backbone.num_features, 2)

    def forward(self, x):
        return self.head(self.backbone(x))


def boxes_to_classify(labels, scores):
    return np.where(np.isin(labels, ['car', 'van']) & (scores >= CFG['min_conf']))[0]


def rescore(labels, scores, selected, p_van):
    a = CFG['alpha']
    scores = scores.copy()
    low = np.isin(labels, ['car', 'van']) & (scores < CFG['min_conf'])
    scores[low] = scores[low] ** a * 0.5 ** (1 - a)
    for j, p in zip(selected, p_van):
        q = float(p if labels[j] == 'van' else 1 - p)
        scores[j] = scores[j] ** a * max(q, 1e-6) ** (1 - a)
    return scores


def crop_image(image_file, boxes):
    image = np.asarray(Image.open(image_file).convert('RGB'))
    crops = [square_crop(image, *box, size=CFG['image_size']) for box in boxes]
    return np.stack(crops) if crops else np.zeros((0, CFG['image_size'], CFG['image_size'], 3), np.uint8)


@torch.no_grad()
def predict_p_van(model, crops):
    mean = torch.tensor([0.485, 0.456, 0.406], device='cuda').view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device='cuda').view(1, 3, 1, 1)
    p = []
    for start in range(0, len(crops), 768):
        x = torch.from_numpy(crops[start:start + 768]).cuda().permute(0, 3, 1, 2).float() / 255
        with torch.autocast('cuda', dtype=torch.bfloat16):
            p.append(model((x - mean) / std).float().softmax(1)[:, 1].cpu())
    return torch.cat(p).numpy() if p else np.zeros(0)


if __name__ == '__main__':
    images = sys.argv[1]
    folder = imagesets.output_dir(images)
    ids, files = imagesets.load(images)
    rows = submission.read(folder / 'calibrated.csv')

    model = CarVanClassifier()
    weights = torch.load(paths.WEIGHTS / CFG['weights'], map_location='cpu', weights_only=False)['state_dict']
    model.load_state_dict({k: v.float() for k, v in weights.items()})
    model = model.cuda().eval()

    out = {}
    pool = Pool(16)
    for start in range(0, len(ids), 64):   # 64 images at a time, so the crops fit in memory
        batch = ids[start:start + 64]
        parsed, selected, jobs = [], [], []
        for image_id in batch:
            labels, scores, boxes = submission.parse(rows[image_id])
            chosen = boxes_to_classify(labels, scores)
            parsed.append((labels, scores, boxes))
            selected.append(chosen)
            jobs.append((files[image_id], boxes[chosen].tolist()))

        crops = pool.starmap(crop_image, jobs)
        p_van = predict_p_van(model, np.concatenate(crops))

        k = 0
        for image_id, (labels, scores, boxes), chosen in zip(batch, parsed, selected):
            new_scores = rescore(labels, scores, chosen, p_van[k:k + len(chosen)])
            k += len(chosen)
            out[image_id] = submission.to_text(labels, new_scores, boxes)
    pool.close()

    submission.write(folder / 'dino.csv', out)

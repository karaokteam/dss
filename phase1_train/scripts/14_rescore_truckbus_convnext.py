"""Stage 4: re-score truck/bus boxes with the ConvNeXt-L classifier.   python scripts/14_rescore_truckbus_convnext.py test

new score = s^0.8 * p^0.2, p = probability of the box's own class (boxes under 0.03 use p = 0.25).
dino.csv -> final_submission.csv
"""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import timm
import torch
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import CLASSES, config, imagesets, paths, submission  # noqa: E402
from roketsan.crops import margin_crop  # noqa: E402

CFG = config.load()['convnext_cls4']


def boxes_to_classify(labels, scores):
    return np.where(np.isin(labels, CFG['classes']) & (scores >= CFG['min_conf']))[0]


def rescore(labels, scores, selected, probabilities):
    a = CFG['alpha']
    scores = scores.copy()
    low = np.isin(labels, CFG['classes']) & (scores < CFG['min_conf'])
    scores[low] = scores[low] ** a * CFG['below_min_prob'] ** (1 - a)
    for j, p in zip(selected, probabilities):
        p_own_class = float(p[CLASSES.index(labels[j])])
        scores[j] = scores[j] ** a * max(p_own_class, 1e-6) ** (1 - a)
    return scores


def crop_image(image_file, boxes):
    image = Image.open(image_file).convert('RGB')
    crops = [margin_crop(image, *box, size=CFG['crop_size']) for box in boxes]
    return np.stack(crops) if crops else np.zeros((0, CFG['crop_size'], CFG['crop_size'], 3), np.uint8)


@torch.no_grad()
def predict(model, crops):
    """Class probabilities, averaged over the crop and its mirror image."""
    mean = torch.tensor([0.485, 0.456, 0.406], device='cuda').view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device='cuda').view(1, 3, 1, 1)
    out = []
    for start in range(0, len(crops), 512):
        x = torch.from_numpy(crops[start:start + 512]).cuda().permute(0, 3, 1, 2).float() / 255
        x = F.interpolate(x, size=(CFG['input_size'], CFG['input_size']), mode='bilinear', align_corners=False)
        x = ((x - mean) / std).contiguous(memory_format=torch.channels_last)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            p = model(x).float().softmax(1) + model(torch.flip(x, dims=(3,))).float().softmax(1)
        out.append((p / 2).cpu())
    return torch.cat(out).numpy() if out else np.zeros((0, 4))


if __name__ == '__main__':
    images = sys.argv[1]
    folder = imagesets.output_dir(images)
    ids, files = imagesets.load(images)
    rows = submission.read(folder / 'dino.csv')

    model = timm.create_model(CFG['backbone'], pretrained=False, num_classes=4)
    model.load_state_dict(torch.load(paths.WEIGHTS / CFG['weights'], map_location='cpu', weights_only=False)['model'])
    model = model.cuda().eval().to(memory_format=torch.channels_last)

    parsed, selected, jobs = [], [], []
    for image_id in ids:
        labels, scores, boxes = submission.parse(rows[image_id])
        chosen = boxes_to_classify(labels, scores)
        parsed.append((labels, scores, boxes))
        selected.append(chosen)
        jobs.append((files[image_id], boxes[chosen].tolist()))
    with Pool(16) as pool:
        crops = pool.starmap(crop_image, jobs)
    probabilities = predict(model, np.concatenate(crops))

    out, k = {}, 0
    for image_id, (labels, scores, boxes), chosen in zip(ids, parsed, selected):
        new_scores = rescore(labels, scores, chosen, probabilities[k:k + len(chosen)])
        k += len(chosen)
        out[image_id] = submission.to_text(labels, new_scores, boxes)

    submission.write(folder / 'final_submission.csv', out)

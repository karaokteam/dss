"""Train the ConvNeXt-L 4-class vehicle classifier (stage 4) on crops of the 70% split's training images."""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import CLASSES, config, paths  # noqa: E402
from roketsan.crops import margin_crop  # noqa: E402

CFG = config.load()['convnext_cls4']
MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda()
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda()


def crop_image(image_file, boxes):
    image = Image.open(image_file).convert('RGB')
    return np.stack([margin_crop(image, x, y, w, h) for x, y, w, h in boxes])


def load_crops(part):
    """Crops and class indices of every ground-truth box in one part of the split."""
    files = {p.stem: p for p in (paths.YOLO_SPLIT / 'images' / part).iterdir()}
    boxes = pd.read_csv(paths.TRAIN_ANNOTATIONS)
    boxes = boxes[boxes.image_id.isin(files) & (boxes.w > 0) & (boxes.h > 0)]
    groups = list(boxes.groupby('image_id'))
    jobs = [(files[image_id], g[['x', 'y', 'w', 'h']].values.tolist()) for image_id, g in groups]
    with Pool(48) as pool:
        crops = pool.starmap(crop_image, jobs)
    labels = [CLASSES.index(label) for _, g in groups for label in g.label]
    return np.concatenate(crops), np.array(labels)


def to_tensor(crops, augment=False):
    x = torch.from_numpy(crops).cuda().permute(0, 3, 1, 2).float() / 255
    x = F.interpolate(x, size=(CFG['input_size'], CFG['input_size']), mode='bilinear', align_corners=False)
    if augment:   # a drone view has no fixed orientation
        x = torch.rot90(x, int(np.random.randint(4)), dims=(2, 3))
        if np.random.rand() < 0.5:
            x = torch.flip(x, dims=(3,))
        contrast = torch.empty(len(x), 1, 1, 1, device='cuda').uniform_(0.8, 1.2)
        brightness = torch.empty(len(x), 1, 1, 1, device='cuda').uniform_(-0.1, 0.1)
        x = ((x - 0.5) * contrast + 0.5 + brightness).clamp(0, 1)
    return ((x - MEAN) / STD).contiguous(memory_format=torch.channels_last)


torch.manual_seed(0)
np.random.seed(0)
train_x, train_y = load_crops('train')
val_x, val_y = load_crops('val')

model = timm.create_model(CFG['backbone'], pretrained=True, num_classes=4, drop_path_rate=0.15)
model = model.cuda().to(memory_format=torch.channels_last)
head = list(model.get_classifier().parameters())
head_ids = {id(p) for p in head}
backbone = [p for p in model.parameters() if id(p) not in head_ids]
optimizer = torch.optim.AdamW([{'params': backbone, 'lr': 5e-5}, {'params': head, 'lr': 5e-4}], weight_decay=0.05)

epochs, batch = 2, 128
steps = epochs * (len(train_y) // batch)
schedule = lambda i: min(1, (i + 1) / 200) * 0.5 * (1 + np.cos(np.pi * min(i, steps) / steps))   # warm-up + cosine
scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, schedule)
loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=0.05)

# rare classes are sampled more often: probability ~ 1 / sqrt(class count)
sample_weight = 1 / np.sqrt(np.bincount(train_y))[train_y]
sample_weight /= sample_weight.sum()

model.train()
for epoch in range(epochs):
    order = np.random.choice(len(train_y), len(train_y) // batch * batch, p=sample_weight)
    for start in range(0, len(order), batch):
        idx = np.sort(order[start:start + batch])
        x, y = to_tensor(train_x[idx], augment=True), torch.from_numpy(train_y[idx]).cuda()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            loss = loss_fn(model(x), y)
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
    print(f'epoch {epoch + 1} loss {loss.item():.3f}')

model.eval()
predictions = []
with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
    for start in range(0, len(val_x), 512):
        x = to_tensor(val_x[start:start + 512])
        p = model(x).float().softmax(1) + model(torch.flip(x, dims=(3,))).float().softmax(1)
        predictions.append(p.argmax(1).cpu())
predictions = torch.cat(predictions).numpy()
for i, name in enumerate(CLASSES):
    print(f'split_val accuracy {name}: {(predictions[val_y == i] == i).mean():.3f}')

paths.WEIGHTS.mkdir(parents=True, exist_ok=True)
torch.save({'model': model.state_dict(), 'classes': CLASSES}, paths.WEIGHTS / CFG['weights'])

"""Car/van classifier: timm backbone + kareli baglam crop'lari.

Opsiyonel:
  --use_mask  4. kanal olarak hedef kutunun maskesi (kirpmada komsu araclar da var, model hangisine bakacagini bilsin)
  --use_size  boyut ozellikleri (en-boy orani, ayni goruntudeki medyan car alanina gore boyut, goruntuye gore boyut)

Colab'da:
  !python train_cls.py --data /content/crops_car_van_sq2 \
      --zip /content/drive/MyDrive/classifier_data/crops_car_van_sq2.zip \
      --split_csv /content/drive/MyDrive/classifier_data/pad20_clean/crops_scored.csv \
      --out /content/drive/MyDrive/classifier_data/runs/convnext_sq2
"""
import argparse
import copy
import json
import math
import os
import random
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

CLASSES = ["car", "van"]
MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="crops.csv + car/ + van/ klasoru")
    p.add_argument("--zip", default=None, help="--data yoksa buradan acilir")
    p.add_argument("--split_csv", required=True, help="image_id + split kolonlu csv (onceki egitimlerle ayni val icin)")
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="convnext_tiny.fb_in22k_ft_in1k")
    p.add_argument("--imgsz", type=int, default=224)
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--batch", type=int, default=128)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--wd", type=float, default=0.05)
    p.add_argument("--car_per_van", type=float, default=2.0, help="train'de her epoch car:van orani")
    p.add_argument("--label_smoothing", type=float, default=0.1)
    p.add_argument("--ema", type=float, default=0.999)
    p.add_argument("--warmup_epochs", type=float, default=1.0)
    p.add_argument("--layer_decay", type=float, default=1.0, help="ViT icin katman bazli lr azaltma (1.0 = kapali)")
    p.add_argument("--drop_path", type=float, default=0.0)
    p.add_argument("--clip_grad", type=float, default=0.0, help="0 = kapali")
    p.add_argument("--use_mask", action="store_true")
    p.add_argument("--use_size", action="store_true")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--resume", action="store_true", help="--out/last.pt varsa kaldigi epoch'tan devam et")
    return p.parse_args()


def size_features(df):
    # rot90 augmentasyonunda w/h yer degistirdigi icin en-boy orani yonsuz: log(uzun/kisa)
    long_side = df[["ow", "oh"]].max(axis=1)
    short_side = df[["ow", "oh"]].min(axis=1)
    area = df["ow"] * df["oh"]
    # drone yuksekligi degistigi icin mutlak boyut yerine ayni goruntudeki car'lara gore boyut
    rel_car = np.log(area / df["med_car_area"]).fillna(0.0)
    return np.stack([
        np.log(long_side / short_side),
        rel_car,
        np.log(area / (df["img_w"] * df["img_h"])),
    ], axis=1).astype(np.float32)


class CropDataset(Dataset):
    def __init__(self, df, root, feats, imgsz, train, use_mask):
        self.df = df.reset_index(drop=True)
        self.root = Path(root)
        self.feats = torch.from_numpy(feats)
        self.labels = torch.tensor([CLASSES.index(c) for c in self.df["label"]])
        self.imgsz = imgsz
        self.train = train
        self.use_mask = use_mask

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        r = self.df.iloc[i]
        s = self.imgsz
        im = Image.open(self.root / r.file).convert("RGB").resize((s, s), Image.BILINEAR)
        x = torch.from_numpy(np.asarray(im, dtype=np.float32) / 255.0).permute(2, 0, 1)

        if self.train:
            # dusuk cozunurluge dayaniklilik: rastgele kucultup geri buyut
            if random.random() < 0.3:
                k = random.uniform(0.25, 0.7)
                small = F.interpolate(x[None], scale_factor=k, mode="bilinear", align_corners=False)
                x = F.interpolate(small, size=(s, s), mode="bilinear", align_corners=False)[0]
            # hafif parlaklik/kontrast
            x = (x - 0.5) * random.uniform(0.8, 1.2) + 0.5 + random.uniform(-0.1, 0.1)
            x = x.clamp(0, 1)

        x = (x - MEAN) / STD

        if self.use_mask:
            k = s / r.side
            m = torch.zeros(1, s, s)
            x1, y1 = int((r.ox - r.x0) * k), int((r.oy - r.y0) * k)
            x2, y2 = math.ceil((r.ox + r.ow - r.x0) * k), math.ceil((r.oy + r.oh - r.y0) * k)
            m[:, max(0, y1):min(s, y2), max(0, x1):min(s, x2)] = 1.0
            x = torch.cat([x, m])

        if self.train:
            # yukaridan cekim: yon anlamsiz -> 8 dihedral donusum (maske de birlikte doner)
            x = torch.rot90(x, random.randint(0, 3), dims=(1, 2))
            if random.random() < 0.5:
                x = torch.flip(x, dims=(2,))

        return x, self.feats[i], self.labels[i]


class Net(nn.Module):
    def __init__(self, name, in_chans, n_size, imgsz, drop_path):
        super().__init__()
        kw = {"drop_path_rate": drop_path}
        if "vit" in name:
            kw["img_size"] = imgsz  # DINOv2 518 ile egitildi; pozisyon gomuleri imgsz'e interpole edilir
        self.backbone = timm.create_model(name, pretrained=True, num_classes=0, in_chans=in_chans, **kw)
        d = self.backbone.num_features
        self.size_mlp = nn.Sequential(nn.Linear(n_size, 64), nn.GELU(), nn.Linear(64, 64)) if n_size else None
        self.head = nn.Linear(d + (64 if n_size else 0), len(CLASSES))

    def forward(self, x, s):
        f = self.backbone(x)
        if self.size_mlp is not None:
            f = torch.cat([f, self.size_mlp(s)], dim=1)
        return self.head(f)


def param_groups(model, lr, wd, layer_decay):
    """AdamW parametre gruplari: norm/bias/token'larda weight decay yok; ViT'te katman bazli lr azaltma.

    backbone.blocks.{i} -> katman i+1, gomme katmanlari (patch_embed, cls_token, pos_embed, reg_token) -> 0,
    geri kalan her sey (son norm, size_mlp, head) -> en ust katman (tam lr).
    """
    blocks = getattr(model.backbone, "blocks", None)
    n_layers = len(blocks) + 1 if blocks is not None and layer_decay < 1.0 else 0
    groups = {}
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        layer = n_layers
        if n_layers:
            if name.startswith("backbone.blocks."):
                layer = int(name.split(".")[2]) + 1
            elif name.startswith(("backbone.patch_embed", "backbone.cls_token", "backbone.pos_embed",
                                  "backbone.reg_token", "backbone.mask_token")):
                layer = 0
        no_wd = p.ndim <= 1 or name.endswith(("cls_token", "pos_embed", "reg_token", "mask_token"))
        key = (layer, no_wd)
        if key not in groups:
            groups[key] = {"params": [], "weight_decay": 0.0 if no_wd else wd,
                           "lr": lr * layer_decay ** (n_layers - layer)}
        groups[key]["params"].append(p)
    return list(groups.values())


@torch.no_grad()
def predict(model, loader, device, tta=False):
    model.eval()
    probs = []
    for x, s, _ in loader:
        x, s = x.to(device, non_blocking=True), s.to(device, non_blocking=True)
        views = [x]
        if tta:
            views = [torch.rot90(v, k, dims=(2, 3)) for v in (x, torch.flip(x, dims=(3,))) for k in range(4)]
        with torch.autocast("cuda", dtype=torch.bfloat16):
            p = torch.stack([model(v, s).float().softmax(1) for v in views]).mean(0)
        probs.append(p[:, 1].cpu())
    return torch.cat(probs).numpy()


def metrics(y, p_van, thr=0.5):
    pred = (p_van >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    van_rec = tp / max(tp + fn, 1)
    van_prec = tp / max(tp + fp, 1)
    return {
        "top1": (tp + tn) / len(y),
        "car_recall": tn / max(tn + fp, 1),
        "van_recall": van_rec,
        "van_precision": van_prec,
        "van_f1": 2 * van_prec * van_rec / max(van_prec + van_rec, 1e-9),
        "cm_true_car": [tn, fp],  # [car tahmini, van tahmini]
        "cm_true_van": [fn, tp],
    }


def main():
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    data = Path(args.data)
    if not (data / "crops.csv").exists():
        shutil.unpack_archive(args.zip, data)

    meta = pd.read_csv(data / "crops.csv")
    meta["image_id"] = meta["image_id"].astype(str)
    split = pd.read_csv(args.split_csv, usecols=["image_id", "split"]).drop_duplicates()
    split["image_id"] = split["image_id"].astype(str)
    val_ids = set(split.loc[split["split"] == "val", "image_id"])
    meta["split"] = np.where(meta["image_id"].isin(val_ids), "val", "train")
    tr, va = meta[meta["split"] == "train"], meta[meta["split"] == "val"]
    print(f"train {tr['label'].value_counts().to_dict()} | val {va['label'].value_counts().to_dict()}")

    feats = size_features(meta)
    f_mean, f_std = feats[meta["split"] == "train"].mean(0), feats[meta["split"] == "train"].std(0) + 1e-6
    feats = (feats - f_mean) / f_std
    tr_idx, va_idx = np.where(meta["split"] == "train")[0], np.where(meta["split"] == "val")[0]

    in_chans = 4 if args.use_mask else 3
    ds_tr = CropDataset(tr, data, feats[tr_idx], args.imgsz, True, args.use_mask)
    ds_va = CropDataset(va, data, feats[va_idx], args.imgsz, False, args.use_mask)

    # her epoch tum van'lar ~1 kez + car_per_van kati rastgele car (her epoch farkli car'lar)
    n_van = int((tr["label"] == "van").sum())
    n_car = len(tr) - n_van
    w = np.where(tr["label"] == "van", 1.0 / n_van, args.car_per_van / n_car)
    n_per_epoch = int(n_van * (1 + args.car_per_van))
    sampler = WeightedRandomSampler(torch.tensor(w, dtype=torch.double), n_per_epoch, replacement=True)
    dl_tr = DataLoader(ds_tr, args.batch, sampler=sampler, num_workers=args.workers,
                       pin_memory=True, drop_last=True, persistent_workers=True)
    dl_va = DataLoader(ds_va, 256, shuffle=False, num_workers=args.workers, pin_memory=True)

    model = Net(args.model, in_chans, 3 if args.use_size else 0, args.imgsz, args.drop_path).to(device)
    print(f"model {args.model} | parametre {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M", flush=True)
    ema = copy.deepcopy(model).eval()
    for p in ema.parameters():
        p.requires_grad_(False)

    opt = torch.optim.AdamW(param_groups(model, args.lr, args.wd, args.layer_decay))
    steps = args.epochs * len(dl_tr)
    warm = max(1, int(args.warmup_epochs * len(dl_tr)))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda i: min(1.0, (i + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(i, steps) / steps)))
    loss_fn = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)

    y_va = ds_va.labels.numpy()
    start_ep, best_f1, log = 1, -1.0, []
    last = out / "last.pt"
    if args.resume and last.exists():
        ck = torch.load(last, map_location="cpu", weights_only=False)
        model.load_state_dict(ck["model"])
        ema.load_state_dict(ck["ema"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        start_ep, best_f1, log = ck["epoch"] + 1, ck["best_f1"], ck["log"]
        print(f"last.pt bulundu, epoch {start_ep}'ten devam ediliyor", flush=True)

    for ep in range(start_ep, args.epochs + 1):
        model.train()
        t0, tot, n = time.time(), 0.0, 0
        for x, s, y in dl_tr:
            x, s, y = x.to(device, non_blocking=True), s.to(device, non_blocking=True), y.to(device, non_blocking=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = loss_fn(model(x, s), y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            if args.clip_grad > 0:
                nn.utils.clip_grad_norm_(model.parameters(), args.clip_grad)
            opt.step()
            sched.step()
            with torch.no_grad():
                for e, m in zip(ema.state_dict().values(), model.state_dict().values()):
                    if e.dtype.is_floating_point:
                        e.mul_(args.ema).add_(m.detach(), alpha=1 - args.ema)
                    else:
                        e.copy_(m)
            tot += loss.item() * len(y)
            n += len(y)

        p_van = predict(ema, dl_va, device)
        m = metrics(y_va, p_van)
        row = {"epoch": ep, "train_loss": tot / n, "sec": round(time.time() - t0),
               **{k: round(v, 4) for k, v in m.items() if not k.startswith("cm")}}
        log.append(row)
        pd.DataFrame(log).to_csv(out / "results.csv", index=False)
        print(" | ".join(f"{k} {v}" for k, v in row.items()), flush=True)

        if m["van_f1"] > best_f1:
            best_f1 = m["van_f1"]
            torch.save({"state_dict": ema.state_dict(), "args": vars(args), "classes": CLASSES,
                        "feat_mean": f_mean, "feat_std": f_std, "epoch": ep}, out / "best.pt")

        # Colab oturumu kesilirse --resume ile devam edebilmek icin; yarim yazilmis dosya kalmasin diye once tmp
        tmp = out / "last.pt.tmp"
        torch.save({"model": model.state_dict(), "ema": ema.state_dict(), "opt": opt.state_dict(),
                    "sched": sched.state_dict(), "epoch": ep, "best_f1": best_f1, "log": log}, tmp)
        os.replace(tmp, last)

    # en iyi model: TTA'siz ve TTA'li son degerlendirme + val tahminleri
    ckpt = torch.load(out / "best.pt", weights_only=False)
    ema.load_state_dict(ckpt["state_dict"])
    final = {}
    for tta in (False, True):
        p_van = predict(ema, dl_va, device, tta=tta)
        final["tta" if tta else "no_tta"] = metrics(y_va, p_van)
        if tta:
            pd.DataFrame({"file": va["file"].values, "label": va["label"].values, "p_van": p_van}).to_csv(
                out / "val_predictions.csv", index=False)
    final["best_epoch"] = ckpt["epoch"]
    (out / "final_metrics.json").write_text(json.dumps(final, indent=2))
    last.unlink(missing_ok=True)  # egitim bitti; optimizer durumu (~5 GB) artik gereksiz
    print("EN IYI EPOCH", ckpt["epoch"])
    for k in ("no_tta", "tta"):
        print(k, json.dumps(final[k]))


if __name__ == "__main__":
    main()

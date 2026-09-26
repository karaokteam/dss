"""Veri dosyası okuyucular — HAZIR (Step 0). Başka modüller dosya okumaz, bunları çağırır.

Dosya formatı beklenenden farklı çıkarsa sadece burası değişir (VERI-1 bulgusu → PR).
"""

import csv
import json
from functools import lru_cache
from pathlib import Path

from agent import config
from agent.schemas import FieldReport, ImageMeta, TrackPoint, ZonesFile

IMAGE_EXTS = (".jpg", ".jpeg", ".png")


@lru_cache
def load_image_meta(path: Path = config.IMAGE_META_PATH) -> dict[str, ImageMeta]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {image_id: ImageMeta(image_id=image_id, **m) for image_id, m in sorted(raw.items())}


@lru_cache
def load_zones(path: Path = config.ZONES_PATH) -> ZonesFile:
    return ZonesFile(**json.loads(Path(path).read_text(encoding="utf-8")))


@lru_cache
def load_tracks(path: Path = config.TRACKS_PATH) -> list[TrackPoint]:
    with open(path, newline="", encoding="utf-8") as f:
        return [
            TrackPoint(track_id=r["track_id"], time=r["time"], lat=float(r["lat"]), lon=float(r["lon"]))
            for r in csv.DictReader(f)
        ]


@lru_cache
def load_reports(path: Path = config.REPORTS_PATH) -> list[FieldReport]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw["reports"] if isinstance(raw, dict) else raw
    return [FieldReport(report_id=f"R{i:03d}", **r) for i, r in enumerate(items)]


def image_path(image_id: str, images_dir: Path = config.IMAGES_DIR) -> Path:
    for ext in IMAGE_EXTS:
        p = Path(images_dir) / f"{image_id}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"{image_id} görüntüsü {images_dir} altında yok")

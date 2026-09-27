"""Ham dosyaları okuyup `models` tiplerine çevirir. Veri kaynaklarına dokunan tek yer burasıdır."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from backend.config import Paths
from backend.engine.models import (
    AltLabel, Base, Corners, Dataset, Detection, ImageMeta, RawPrediction, Report, Source,
    Track, TrackPoint, Zone, parse_hhmm,
)


def _read_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _latlon(pair) -> tuple[float, float]:
    return float(pair[0]), float(pair[1])


def load_zones(path: Path) -> tuple[Base, tuple[Zone, ...]]:
    raw = _read_json(path)
    b = raw["base"]
    base = Base(name=b["name"], lat=float(b["lat"]), lon=float(b["lon"]))
    zones = tuple(Zone(name=z["name"], lat=float(z["center"][0]), lon=float(z["center"][1]))
                  for z in raw["zones"])
    return base, zones


def load_images(meta_path: Path, images_dir: Path, annotated_dir: Path | None = None) -> tuple[ImageMeta, ...]:
    raw = _read_json(meta_path)
    images = []
    for image_id, m in raw.items():
        c = m["corner_coordinates"]
        annotated = annotated_dir / f"{image_id}.jpg" if annotated_dir else None
        images.append(ImageMeta(
            id=image_id,
            width_px=int(m["width_px"]),
            height_px=int(m["height_px"]),
            capture_min=parse_hhmm(m["capture_time"]),
            corners=Corners(top_left=_latlon(c["top_left"]), top_right=_latlon(c["top_right"]),
                            bottom_left=_latlon(c["bottom_left"]), bottom_right=_latlon(c["bottom_right"])),
            file=images_dir / f"{image_id}.jpg",
            annotated_file=annotated if annotated and annotated.exists() else None,
        ))
    return tuple(sorted(images, key=lambda i: (i.capture_min, i.id)))


def load_detections(path: Path) -> tuple[Detection, ...]:
    raw = _read_json(path)
    detections = []
    for img in raw["images"]:
        for d in img["detections"]:
            detections.append(Detection(
                id=d["id"],
                image_id=img["image_id"],
                label=d["label"],
                confidence=float(d["confidence"]),
                bbox_xywh=tuple(float(v) for v in d["bbox_xywh"]),
                center_px=tuple(float(v) for v in d["center_px"]),
                lat=float(d["lat"]),
                lon=float(d["lon"]),
                alt_labels=tuple(AltLabel(a["label"], float(a["confidence"])) for a in d.get("alt_labels", [])),
            ))
    return tuple(detections)


def load_raw_predictions(path: Path) -> dict[str, tuple[RawPrediction, ...]]:
    """stage2_final.csv: görüntü başına "label conf x y w h ..." dizisi (eşik altı tahminler dahil)."""
    out: dict[str, tuple[RawPrediction, ...]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            parts = row["PredictionString"].split()
            out[row["image_id"]] = tuple(
                RawPrediction(label=parts[i], confidence=float(parts[i + 1]),
                              bbox_xywh=tuple(float(v) for v in parts[i + 2:i + 6]))
                for i in range(0, len(parts) - 5, 6))
    return out


def load_tracks(path: Path) -> tuple[Track, ...]:
    points: dict[str, list[TrackPoint]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            points[row["track_id"]].append(
                TrackPoint(t=parse_hhmm(row["time"]), lat=float(row["lat"]), lon=float(row["lon"])))
    return tuple(Track(id=tid, points=tuple(sorted(pts, key=lambda p: p.t)))
                 for tid, pts in sorted(points.items()))


def load_reports(path: Path) -> tuple[Report, ...]:
    raw = _read_json(path)
    return tuple(Report(id=f"R{i + 1:03d}", index=i, t=parse_hhmm(r["time"]),
                        source=Source(r["source"]), text=r["text"].strip())
                 for i, r in enumerate(raw))


def _attach_track_images(tracks: tuple[Track, ...], images: tuple[ImageMeta, ...],
                         warnings: list[str]) -> tuple[Track, ...]:
    """Her track, son noktası bir görüntünün çekim anına denk gelecek şekilde kurgulanmış."""
    by_time: dict[int, list[str]] = defaultdict(list)
    for img in images:
        by_time[img.capture_min].append(img.id)
    result = []
    for tr in tracks:
        candidates = by_time.get(tr.end_min, [])
        if len(candidates) != 1:
            # Birden fazla aday footprint'e göre Step 3'te çözülür; yoksa track görüntüsüz kalır.
            warnings.append(f"{tr.id}: bitiş saatinde {len(candidates)} görüntü var")
        image_id = candidates[0] if len(candidates) == 1 else None
        result.append(Track(id=tr.id, points=tr.points, image_id=image_id))
    return tuple(result)


def _check_detections(detections: tuple[Detection, ...], images: tuple[ImageMeta, ...],
                      warnings: list[str]) -> None:
    known = {i.id for i in images}
    unknown = sorted({d.image_id for d in detections} - known)
    if unknown:
        warnings.append(f"Meta'sı olmayan görüntülerde tespit: {unknown}")


def load_dataset(paths: Paths) -> Dataset:
    warnings: list[str] = []
    base, zones = load_zones(paths.zones)
    images = load_images(paths.image_meta, paths.images, paths.annotated_images)
    detections = load_detections(paths.detections)
    _check_detections(detections, images, warnings)
    tracks = _attach_track_images(load_tracks(paths.tracks), images, warnings)
    reports = load_reports(paths.reports)
    return Dataset(base=base, zones=zones, images=images, detections=detections,
                   tracks=tracks, reports=reports, warnings=tuple(warnings))

"""
Sahibi : Kişi 4
Görev  : Bölge adıyla yazılmış raporlar için rapor anındaki bölge durumu

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    track_classes(D, dets_by_image) -> dict[track_id, TrackClass]
    zone_checks_for(report, D, classes, dets_by_image) -> ZoneChecks

"Kuzey Yolu'nda ağır araç yok", "trafik normal" gibi iddialar tek bir karede değil, bölgenin
tamamında ve rapor anında ölçülür (RAPOR_DOGRULAMA.md §5):
  * Bölge = üsse göre yön sektörü; track noktalarında en yakın bölge merkeziyle %100 aynı.
  * Pencere = rapor anı ± 15 dk.
  * Track'lerin sınıfı yok: her track'e, bir çekim anında 3 m içinde eşleştiği tespitin sınıfı
    taşınır (conf >= 0,10; track desteği düşük güvenli tespiti de kabul ettirir). 226 track'in ~195'i.
  * Anomali adayları: sert bayrak koşulları (docs/ARCHITECTURE.md §7) bölgedeki her track için
    rapor anında değerlendirilir. Eşikler Kişi 3'ün flags.py'si hazır olunca oradan okunmalı.
Hüküm vermez, yalnızca ölçer. ZoneChecks şemada henüz yok (öneri: docs/SCHEMA_PROPOSAL_REPORTS.md).
Asimetri: bölgede ağır araç görmek "yok" iddiasını çürütür; görmemek tam doğrulamaz, çünkü park
halindeki araçların track'i olmayabilir.
"""
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from dss.reports.claims import hm, norm, parse_claim
from dss.schemas import ReportEv, VehicleClass

if TYPE_CHECKING:
    from dss.evidence.builder import Data

WINDOW_MIN = 15
RELATED_WINDOW_MIN = 60
CLASS_LINK_M = 3.0
CLASS_MIN_CONF = 0.10
DETECTION_CONF = 0.25
MOVING_MPS = 1.0
STOP_MPS = 0.5
HEAVY = ("truck", "bus")

# docs/ARCHITECTURE.md §7 — Kişi 3'ün flags.py'si hazır olunca oradan okunacak
ETA_MIN = 10
NEAR_APPROACH_M, NEAR_APPROACH_MPS = 1500, 1.0
HEAVY_NEAR_M = 3000
LONG_STOP_MIN, LONG_STOP_NEAR_M = 30, 2000


class TrackClass(BaseModel):
    label: VehicleClass
    conf: float
    image_id: str


class ZoneVehicle(BaseModel):
    track_id: str
    label: Optional[VehicleClass] = None            # taşınan sınıf; None = bilinmiyor
    label_conf: Optional[float] = None
    at: str                                         # ölçüm anı (pencere içinde rapora en yakın nokta)
    dist_to_base_m: int
    speed_15m_mps: Optional[float] = None
    approach_30m_mps: Optional[float] = None        # + ise üsse yaklaşıyor
    flags: list[str] = []                           # sağlanan sert bayrak koşulları


class ZoneImage(BaseModel):
    image_id: str
    capture_time: str
    heavy_detections: int                           # conf >= 0,25 ya da track destekli truck/bus


class ZoneChecks(BaseModel):
    """Bölge raporunun anındaki bölge durumu. Tüm sayılar koddan gelir."""
    zone: str
    window: str                                     # "10:05-10:35"
    vehicles_seen: int                              # pencerede bölgede görülen track sayısı
    moving: int                                     # bunlardan >= 1 m/s hareket eden
    unknown_class: int                              # sınıfı taşınamayan track
    heavy: list[ZoneVehicle] = []                   # bölgedeki truck/bus
    anomalies: list[ZoneVehicle] = []               # en az bir sert bayrak koşulu sağlayanlar
    zone_images: list[ZoneImage] = []               # pencerede çekilen bölge görüntüleri
    radio_gap_reports: list[str] = []               # bölgede telsiz kopukluğu bildiren raporlar (±60 dk)
    related_reports: list[str] = []                 # aynı bölge hakkında diğer raporlar (±60 dk)


def load_detections_file(path: str | Path) -> dict[str, list[dict]]:
    """Kişi 1 çıktısı (data/image_box_and_reports/*.json) -> {image_id: [{label, conf, lat, lon}]}."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {img["image_id"]: [{"label": d["label"], "conf": d["confidence"], "lat": d["lat"], "lon": d["lon"]}
                              for d in img["detections"]] for img in raw["images"]}


def _links(D: "Data", image_id: str, dets: list[dict], min_conf: float) -> list[tuple[str, dict, float]]:
    """Çekim anındaki track'ler ile tespitlerin birebir, mesafe sıralı eşleşmesi (<= CLASS_LINK_M)."""
    at = D.tracks[D.tracks.t == hm(D.meta[image_id]["capture_time"])]
    pairs = []
    for d in dets:
        if d["conf"] < min_conf:
            continue
        dx, dy = D.xy(d["lat"], d["lon"])
        for tid, x, y in zip(at.track_id, at.x, at.y, strict=True):
            if (dist := math.hypot(x - dx, y - dy)) <= CLASS_LINK_M:
                pairs.append((dist, tid, d))
    used_t, used_d, out = set(), set(), []
    for dist, tid, d in sorted(pairs, key=lambda p: p[0]):
        if tid not in used_t and id(d) not in used_d:
            used_t.add(tid); used_d.add(id(d)); out.append((tid, d, dist))
    return out


def track_classes(D: "Data", dets_by_image: dict[str, list[dict]]) -> dict[str, TrackClass]:
    classes: dict[str, TrackClass] = {}
    for image_id, dets in dets_by_image.items():
        if image_id not in D.meta:
            continue
        for tid, d, _ in _links(D, image_id, dets, CLASS_MIN_CONF):
            if tid not in classes or d["conf"] > classes[tid].conf:
                classes[tid] = TrackClass(label=d["label"], conf=round(d["conf"], 2), image_id=image_id)
    return classes


def _fmt(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _vehicle(tid: str, s: dict[int, tuple[float, float, float]], ref: int,
             cls: TrackClass | None) -> ZoneVehicle:
    x, y, d = s[ref]
    speed = math.hypot(x - s[ref - 15][0], y - s[ref - 15][1]) / 900 if ref - 15 in s else None
    approach = (s[ref - 30][2] - d) / 1800 if ref - 30 in s else None
    flags = []
    if approach and approach > 0.3 and d / approach / 60 < ETA_MIN:
        flags.append("YAKIN_VARIS")
    elif approach and d < NEAR_APPROACH_M and approach > NEAR_APPROACH_MPS:
        flags.append("YAKIN_YAKLASMA")
    if cls and cls.label in HEAVY and d < HEAVY_NEAR_M:
        flags.append("AGIR_ARAC_YAKIN")
    stop, t = 0, ref  # ölçüm anında süren bekleme
    while t - 5 in s and math.hypot(s[t][0] - s[t - 5][0], s[t][1] - s[t - 5][1]) / 300 < STOP_MPS:
        stop, t = stop + 5, t - 5
    if stop >= LONG_STOP_MIN and d < LONG_STOP_NEAR_M:
        flags.append("UZUN_BEKLEME_YAKIN")
    return ZoneVehicle(track_id=tid, label=cls.label if cls else None, label_conf=cls.conf if cls else None,
                       at=_fmt(ref), dist_to_base_m=int(d),
                       speed_15m_mps=round(speed, 1) if speed is not None else None,
                       approach_30m_mps=round(approach, 2) if approach is not None else None, flags=flags)


def zone_checks_for(report: ReportEv, D: "Data", classes: dict[str, TrackClass],
                    dets_by_image: dict[str, list[dict]] | None = None) -> ZoneChecks:
    zone = parse_claim(report.text, D.zones).zone
    if zone is None:
        raise ValueError(f"{report.report_id}: bölge adı içermiyor")
    t = hm(report.time)
    lo, hi = t - WINDOW_MIN, t + WINDOW_MIN

    win = D.tracks[D.tracks.t.between(lo, hi)]
    in_zone: dict[str, list[int]] = {}   # track -> bölgedeyken pencere içindeki anları
    for tid, k, la, lon in zip(win.track_id, win.t, win.lat, win.lon, strict=True):
        if D.zone_of(la, lon) == zone:
            in_zone.setdefault(tid, []).append(int(k))
    vehicles = []
    for tid in sorted(in_zone):
        tr = D.tracks[D.tracks.track_id == tid]
        s = {int(k): (float(x), float(y), float(d)) for k, x, y, d in zip(tr.t, tr.x, tr.y, tr.d, strict=True)}
        ref = min(in_zone[tid], key=lambda k: (abs(k - t), k))
        vehicles.append(_vehicle(tid, s, ref, classes.get(tid)))

    images = []
    for image_id, m in D.meta.items():
        c = m["corner_coordinates"]
        center = ((c["top_left"][0] + c["bottom_left"][0]) / 2, (c["top_left"][1] + c["top_right"][1]) / 2)
        if D.zone_of(*center) != zone or not lo <= hm(m["capture_time"]) <= hi:
            continue
        dets = (dets_by_image or {}).get(image_id, [])
        supported = {id(d) for _, d, _ in _links(D, image_id, dets, CLASS_MIN_CONF)}
        heavy = sum(1 for d in dets if d["label"] in HEAVY and (d["conf"] >= DETECTION_CONF or id(d) in supported))
        images.append(ZoneImage(image_id=image_id, capture_time=m["capture_time"], heavy_detections=heavy))

    radio, related = [], []
    for idx, r in enumerate(D.reports, 1):
        rid = f"R{idx:03d}"
        if rid == report.report_id or norm(zone) not in norm(r["text"]):
            continue
        if abs(hm(r["time"]) - t) <= RELATED_WINDOW_MIN:
            (radio if "telsiz" in norm(r["text"]) else related).append(rid)

    return ZoneChecks(
        zone=zone, window=f"{_fmt(lo)}-{_fmt(hi)}", vehicles_seen=len(vehicles),
        moving=sum(1 for v in vehicles if (v.speed_15m_mps or 0) >= MOVING_MPS),
        unknown_class=sum(1 for v in vehicles if v.label is None),
        heavy=[v for v in vehicles if v.label in HEAVY],
        anomalies=[v for v in vehicles if v.flags],
        zone_images=sorted(images, key=lambda i: i.capture_time),
        radio_gap_reports=radio, related_reports=related)

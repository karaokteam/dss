"""Alan sorgusu: bir noktanın çevresinde, bir zaman aralığında hangi araçlar vardı?

Neden tool: Raporlardaki konumlar bulanıktır ("civarında", "yakınında", 4 ondalık ≈ ±6 m) ve araç rapor ile
çekim arasında yer değiştirmiş olabilir. Kanıt dosyası sabit yarıçap/zamanla bağlar; bağlanamayan ya da şüpheli
bir iddiada NEREYE, NE ZAMAN ve NE KADAR GENİŞ bakılacağına agent karar verir.
"""

from __future__ import annotations

from typing import Literal

from backend.config import settings
from backend.engine.agent.tools import tool
from backend.engine.analysis.consistency import HEAVY, get_context
from backend.engine.geo.geometry import distance_m, distance_to_footprint_m
from backend.engine.models import fmt_hhmm, parse_hhmm

VehicleFilter = Literal["car", "van", "truck", "bus", "heavy"]


def _type_ok(label: str | None, wanted: str | None) -> bool:
    if wanted is None:
        return True
    if label is None:
        return True   # etiketsiz track (tespitsiz) filtreyle elenmez; agent kendisi değerlendirir
    return label in HEAVY if wanted == "heavy" else label == wanted


@tool
def vehicles_in_area(lat: float, lon: float, radius_m: float, time_from: str, time_to: str,
                     vehicle_type: VehicleFilter | None = None) -> dict:
    """Bir noktanın çevresinde, verilen zaman aralığında bulunan araçları listeler: hareket kaydı olanlar
    (ne zaman girdi/çıktı, en yakın mesafe, durumu) ve o aralıkta çekilmiş görüntülerde görülen track'siz
    (park halinde) araçlar. Rapordaki aracın başka yerde/zamanda olup olmadığını, bir noktada araç toplanıp
    toplanmadığını veya bir iddianın daha geniş bir alanda doğrulanıp doğrulanmadığını sınamak için kullan.

    Args:
        lat: Merkez enlemi (WGS84).
        lon: Merkez boylamı (WGS84).
        radius_m: Arama yarıçapı, metre (en fazla 2000).
        time_from: Başlangıç saati "HH:MM".
        time_to: Bitiş saati "HH:MM" (aralık en fazla 180 dakika).
        vehicle_type: İsteğe bağlı tip filtresi; "heavy" = truck veya bus.
    """
    cfg = settings.agent
    t0, t1 = parse_hhmm(time_from), parse_hhmm(time_to)
    if t1 < t0:
        return {"error": "time_to, time_from'dan önce olamaz"}
    if t1 - t0 > cfg.area_max_window_min:
        return {"error": f"zaman aralığı en fazla {cfg.area_max_window_min} dk olabilir"}
    if not 0 < radius_m <= cfg.area_max_radius_m:
        return {"error": f"radius_m 0 ile {cfg.area_max_radius_m:.0f} arasında olmalı"}

    ctx = get_context()
    repo = ctx.repo
    tracked = []
    for tr in repo.tracks():
        pts = [p for p in tr.points if t0 <= p.t <= t1]
        inside = [(p, distance_m(lat, lon, p.lat, p.lon)) for p in pts]
        inside = [(p, d) for p, d in inside if d <= radius_m]
        if not inside:
            continue
        label = ctx.label_of_track(tr.id)
        if not _type_ok(label, vehicle_type):
            continue
        first, last = inside[0][0], inside[-1][0]
        moved_inside = any(distance_m(a.lat, a.lon, b.lat, b.lon) > settings.kinematics.move_step_m
                           for (a, _), (b, _) in zip(inside, inside[1:]))
        before = tr.position_at(first.t - settings.kinematics.step_min)
        tracked.append({
            "track_id": tr.id,
            "label": label,
            "detection_id": ctx.track_det.get(tr.id),
            "image_id": tr.image_id,
            "present": f"{first.time}–{last.time}",
            "min_dist_m": round(min(d for _, d in inside)),
            "arrived_during_window": first.t > t0 and before is not None
                                     and distance_m(lat, lon, before.lat, before.lon) > radius_m,
            "left_during_window": last.t < min(t1, tr.end_min),
            "moved_inside": moved_inside,
            "track_ends_at": tr.last.time,
        })
    tracked.sort(key=lambda x: (x["min_dist_m"], x["track_id"]))

    parked = []
    floor = settings.match.low_confidence
    for img in repo.images():
        if not t0 <= img.capture_min <= t1 or distance_to_footprint_m(img, lat, lon) > radius_m:
            continue
        for det in repo.detections_for(img.id):
            if det.id in ctx.det_track or det.confidence < floor or not _type_ok(det.label, vehicle_type):
                continue
            d = distance_m(lat, lon, det.lat, det.lon)
            if d <= radius_m:
                parked.append({"detection_id": det.id, "label": det.label, "confidence": round(det.confidence, 2),
                               "seen_at": img.capture_time, "image_id": img.id, "dist_m": round(d)})
    parked.sort(key=lambda x: (x["dist_m"], x["detection_id"]))

    n = cfg.tool_max_items
    return {
        "query": {"lat": lat, "lon": lon, "radius_m": radius_m, "window": f"{fmt_hhmm(t0)}–{fmt_hhmm(t1)}",
                  "vehicle_type": vehicle_type},
        "tracked_count": len(tracked),
        "tracked": tracked[:n],
        "parked_count": len(parked),
        "parked": parked[:n],
        "note": ("Track'siz araçlar yalnızca bu aralıkta çekilmiş görüntülerde ve güveni ≥ "
                 f"{floor:.2f} olanlardır; görüntü dışındaki park halinde araçlar görünmez."),
        **({"truncated": True} if len(tracked) > n or len(parked) > n else {}),
    }

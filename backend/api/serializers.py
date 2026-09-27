"""Motor tipleri → API JSON. API sözleşmesi tek yerde (STRUCTURE.md §5)."""

from __future__ import annotations

from backend.engine import pipeline
from backend.engine.analysis.consistency import EvidenceContext, check_report, report_status
from backend.engine.geo.geometry import dist_to_base_m
from backend.engine.geo.zones import nearest_zone
from backend.engine.models import ImageMeta, Track

LEVELS = ["critical", "high", "medium", "low"]


def level_rank(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else len(LEVELS)


def image_urls(image_id: str) -> dict:
    return {"raw": f"/api/images/{image_id}/file?variant=raw",
            "annotated": f"/api/images/{image_id}/file?variant=annotated"}


def effective_risk(image_id: str) -> tuple[str, bool, dict | None]:
    """Görüntünün geçerli riski: güncel agent sonucu varsa o, yoksa temel (Katman 1)."""
    assessment = pipeline.load_assessment(image_id)
    if assessment and pipeline.is_current(assessment):
        return assessment["overall_risk"], True, assessment
    return pipeline.build_dossier(image_id).max_risk.value, False, None


def image_summary(ctx: EvidenceContext, img: ImageMeta) -> dict:
    d = pipeline.build_dossier(img.id)
    risk, assessed, assessment = effective_risk(img.id)
    return {
        "id": img.id, "capture_time": img.capture_time, "zone": d.zone,
        "center": {"lat": img.center[0], "lon": img.center[1]},
        "bounds": [[img.lat_bounds[0], img.lon_bounds[0]], [img.lat_bounds[1], img.lon_bounds[1]]],
        "dist_to_base_m": round(d.dist_to_base_m),
        "vehicle_count": sum(1 for v in d.vehicles if not v.vehicle_id.startswith("track:")),
        "max_risk": risk, "baseline_max_risk": d.max_risk.value, "assessed": assessed,
        "fallback": bool(assessment and assessment["trace"].get("fallback")),
        "anomaly_count": len(d.anomalies),
        "summary": assessment["summary"] if assessment else None,
        "urls": image_urls(img.id),
    }


def image_detail(ctx: EvidenceContext, img: ImageMeta) -> dict:
    d = pipeline.build_dossier(img.id)
    match = ctx.matches[img.id]
    corners = img.corners
    return {
        **image_summary(ctx, img),
        "width_px": img.width_px, "height_px": img.height_px,
        "corners": {"top_left": corners.top_left, "top_right": corners.top_right,
                    "bottom_left": corners.bottom_left, "bottom_right": corners.bottom_right},
        "footprint_m": d.footprint_m,
        "detections": [{
            "id": v.vehicle_id, "label": v.label, "confidence": v.confidence,
            "bbox_xywh": v.bbox_xywh, "lat": v.lat, "lon": v.lon,
            "alt_labels": [a.to_dict() for a in v.alt_labels],
            "track_id": v.track_id, "match_dist_m": v.match_dist_m, "flags": list(v.flags),
            "baseline_risk": v.baseline_risk.level.value, "baseline_score": v.baseline_risk.score,
            "is_missed_track": v.vehicle_id.startswith("track:"),
        } for v in d.vehicles],
        "unmatched_tracks": [u.to_dict() for u in match.unmatched_tracks],
    }


def track_json(ctx: EvidenceContext, track: Track, full: bool = True) -> dict:
    base = ctx.repo.base
    kin = ctx.kinematics.get(track.id)
    det = ctx.track_det.get(track.id)
    out = {
        "track_id": track.id, "image_id": track.image_id, "detection_id": det,
        "label": ctx.label_of_track(track.id),
        "start": track.points[0].time, "end": track.last.time,
        "last": {"lat": track.last.lat, "lon": track.last.lon},
    }
    if full:
        out["points"] = [{"time": p.time, "lat": p.lat, "lon": p.lon,
                          "dist_to_base_m": round(dist_to_base_m(base, p.lat, p.lon), 1)} for p in track.points]
        out["kinematics"] = kin.to_dict() if kin else None
    return out


def report_json(ctx: EvidenceContext, report_id: str, full: bool = False) -> dict:
    r, c, links = ctx.repo.report(report_id), ctx.claims[report_id], ctx.links[report_id]
    checks = check_report(ctx, r)
    out = {
        "id": r.id, "time": r.time, "source": r.source.value, "text": r.text,
        "category": c.category,
        "coord": {"lat": c.lat, "lon": c.lon} if c.lat is not None else None,
        "claim": {k: v for k, v in c.to_dict().items()
                  if k not in ("report_id", "category", "lat", "lon", "coord_precision_m")},
        "links": {"images": [i.image_id for i in links.images], "tracks": [t.track_id for t in links.tracks],
                  "zone": links.zone},
        "status": report_status(checks).value,
        "checks": [{"claim_type": ch.claim_type.value, "status": ch.status.value, "reason": ch.reason}
                   for ch in checks],
    }
    if full:
        out["links_detail"] = links.to_dict()
        out["checks"] = [ch.to_dict() for ch in checks]
    return out


def zone_of(ctx: EvidenceContext, lat: float, lon: float) -> str:
    return nearest_zone(lat, lon, ctx.repo.zones)[0].name

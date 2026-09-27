"""/tracks?time=HH:MM | ?image_id=,  /tracks/<id>"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.api.app import ApiError
from backend.api.serializers import track_json, zone_of
from backend.engine import pipeline
from backend.engine.analysis.consistency import get_context
from backend.engine.models import fmt_hhmm, parse_hhmm

bp = Blueprint("tracks", __name__)


def _vehicle_risk(image_id: str | None, track_id: str) -> str | None:
    """Track'in görüntüdeki aracının geçerli riski (agent sonucu varsa o, yoksa temel)."""
    if not image_id:
        return None
    assessment = pipeline.load_assessment(image_id)
    if assessment and pipeline.is_current(assessment):
        v = next((v for v in assessment["vehicles"] if v["track_id"] == track_id), None)
        if v:
            return v["risk_level"]
    d = pipeline.build_dossier(image_id)
    v = next((v for v in d.vehicles if v.track_id == track_id), None)
    return v.baseline_risk.level.value if v else None


@bp.get("/tracks")
def list_tracks():
    ctx = get_context()
    if "time" in request.args:
        t = parse_hhmm(request.args["time"])
        zone_filter = request.args.get("zone")
        points = []
        for tr, p in ctx.repo.tracks_active_at(t):
            k = ctx.kinematics[tr.id]
            zone = zone_of(ctx, p.lat, p.lon)
            if zone_filter and zone != zone_filter:
                continue
            points.append({"track_id": tr.id, "lat": p.lat, "lon": p.lon, "zone": zone,
                           "label": ctx.label_of_track(tr.id),
                           "image_id": tr.image_id, "ends_at": tr.last.time,
                           "consistent_approach": k.consistent_approach,
                           "risk_level": _vehicle_risk(tr.image_id, tr.id)})
        return jsonify({"time": fmt_hhmm(t), "points": points})
    if request.args.get("all"):
        # Tüm gün oynatma: 226 track'in noktaları tek istekte (~5,6 bin nokta)
        items = []
        for tr in ctx.repo.tracks():
            k = ctx.kinematics[tr.id]
            items.append({"track_id": tr.id, "image_id": tr.image_id, "label": ctx.label_of_track(tr.id),
                          "risk_level": _vehicle_risk(tr.image_id, tr.id),
                          "consistent_approach": k.consistent_approach,
                          "circling": k.circling, "circling_window": k.circling_window,
                          "points": [{"time": p.time, "lat": p.lat, "lon": p.lon} for p in tr.points]})
        return jsonify({"items": items})
    if "image_id" in request.args:
        image_id = request.args["image_id"]
        tracks = ctx.repo.tracks_for_image(image_id)
        return jsonify({"image_id": image_id,
                        "items": [{**track_json(ctx, tr), "risk_level": _vehicle_risk(image_id, tr.id)}
                                  for tr in tracks]})
    raise ApiError(400, "bad_request", "time=HH:MM ya da image_id parametresi gerekli")


@bp.get("/tracks/<track_id>")
def get_track(track_id: str):
    ctx = get_context()
    tr = ctx.repo.track(track_id)
    return jsonify({**track_json(ctx, tr), "risk_level": _vehicle_risk(tr.image_id, tr.id)})

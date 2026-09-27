"""/images, /images/<id>, /images/<id>/file, /images/<id>/dossier, /images/<id>/assessment"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from backend.api.app import ApiError
from backend.api.serializers import image_detail, image_summary, level_rank
from backend.engine import pipeline
from backend.engine.analysis.consistency import get_context
from backend.engine.models import parse_hhmm

bp = Blueprint("images", __name__)


@bp.get("/images")
def list_images():
    ctx = get_context()
    t0 = parse_hhmm(request.args["time_from"]) if "time_from" in request.args else 0
    t1 = parse_hhmm(request.args["time_to"]) if "time_to" in request.args else 24 * 60
    zone = request.args.get("zone")
    min_risk = request.args.get("min_risk")
    items = []
    for img in ctx.repo.images():
        if not t0 <= img.capture_min <= t1:
            continue
        s = image_summary(ctx, img)
        if zone and s["zone"] != zone:
            continue
        if min_risk and level_rank(s["max_risk"]) > level_rank(min_risk):
            continue
        items.append(s)
    return jsonify({"total": len(items), "items": items})


@bp.get("/images/<image_id>")
def get_image(image_id: str):
    ctx = get_context()
    return jsonify(image_detail(ctx, ctx.repo.image(image_id)))


@bp.get("/images/<image_id>/file")
def image_file(image_id: str):
    img = get_context().repo.image(image_id)
    variant = request.args.get("variant", "raw")
    if variant not in ("raw", "annotated"):
        raise ApiError(400, "bad_request", "variant 'raw' ya da 'annotated' olmalı")
    path = img.annotated_file if variant == "annotated" else img.file
    if path is None or not path.exists():
        raise ApiError(404, "not_found", f"{image_id} için {variant} görüntü yok")
    response = send_file(path, mimetype="image/jpeg", max_age=3600)
    return response


@bp.get("/images/<image_id>/dossier")
def dossier(image_id: str):
    get_context().repo.image(image_id)
    return jsonify(pipeline.build_dossier(image_id).to_dict())


@bp.get("/images/<image_id>/assessment")
def assessment(image_id: str):
    get_context().repo.image(image_id)
    result = pipeline.load_assessment(image_id)
    if result is None:
        raise ApiError(404, "not_assessed", f"{image_id} henüz değerlendirilmedi (POST /api/images/{image_id}/assess)")
    return jsonify({**result, "current": pipeline.is_current(result)})

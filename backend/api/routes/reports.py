"""/reports (filtreli), /reports/<id>"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.api.serializers import report_json
from backend.engine.analysis.consistency import get_context
from backend.engine.models import parse_hhmm

bp = Blueprint("reports", __name__)


@bp.get("/reports")
def list_reports():
    ctx = get_context()
    a = request.args
    t0 = parse_hhmm(a["time_from"]) if "time_from" in a else 0
    t1 = parse_hhmm(a["time_to"]) if "time_to" in a else 24 * 60
    items = []
    for r in ctx.repo.reports_between(t0, t1):
        j = report_json(ctx, r.id)
        if a.get("source") and j["source"] != a["source"]:
            continue
        if a.get("category") and j["category"] != a["category"]:
            continue
        if a.get("claim_type") and a["claim_type"] not in j["claim"]["claim_types"]:
            continue
        if a.get("status") and j["status"] != a["status"]:
            continue
        if a.get("image_id") and a["image_id"] not in j["links"]["images"]:
            continue
        if a.get("zone") and j["links"]["zone"] != a["zone"]:
            continue
        items.append(j)
    return jsonify({"total": len(items), "items": items})


@bp.get("/reports/<report_id>")
def get_report(report_id: str):
    ctx = get_context()
    ctx.repo.report(report_id)
    return jsonify(report_json(ctx, report_id, full=True))

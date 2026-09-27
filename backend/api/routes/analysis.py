"""Analiz: POST /images/<id>/assess, POST /assess, /jobs, /jobs/<id>, /jobs/<id>/events (SSE), /alerts, /timeline"""

from __future__ import annotations

import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from backend.api.app import ApiError
from backend.api.jobs import get_jobs
from backend.api.serializers import LEVELS, effective_risk, level_rank, report_json
from backend.engine import pipeline
from backend.engine.analysis.consistency import get_context

bp = Blueprint("analysis", __name__)
_EFFORTS = ("low", "high", "max")


def _options() -> tuple[bool, str | None]:
    body = request.get_json(silent=True) or {}
    force = bool(body.get("force", False))
    effort = body.get("reasoning_effort")
    if effort is not None and effort not in _EFFORTS:
        raise ApiError(400, "bad_request", f"reasoning_effort {list(_EFFORTS)} içinden olmalı")
    return force, effort


def _accepted(job, created: bool):
    return jsonify({**job.to_dict(), "created": created, "job_url": f"/api/jobs/{job.id}"}), 202


@bp.post("/images/<image_id>/assess")
def assess_image(image_id: str):
    get_context().repo.image(image_id)
    force, effort = _options()
    return _accepted(*get_jobs().submit([image_id], force=force, effort=effort))


@bp.post("/assess")
def assess_many():
    ctx = get_context()
    body = request.get_json(silent=True) or {}
    ids = body.get("image_ids") or [img.id for img in ctx.repo.images()]
    if not isinstance(ids, list):
        raise ApiError(400, "bad_request", "image_ids bir liste olmalı")
    for i in ids:
        ctx.repo.image(i)
    force, effort = _options()
    return _accepted(*get_jobs().submit(ids, force=force, effort=effort))


@bp.get("/jobs")
def list_jobs():
    return jsonify({"items": [j.to_dict() for j in get_jobs().list()]})


@bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    return jsonify(get_jobs().get(job_id).to_dict())


@bp.get("/jobs/<job_id>/events")
def job_events(job_id: str):
    """Server-Sent Events. Yeniden bağlanmada Last-Event-ID (ya da ?after=) ile kalınan yerden devam eder."""
    job = get_jobs().get(job_id)
    after = int(request.headers.get("Last-Event-ID") or request.args.get("after") or 0)

    def gen():
        yield "retry: 3000\n\n"
        for e in job.stream(after=after):
            if e is None:
                yield ": keepalive\n\n"
                continue
            yield f"id: {e['id']}\nevent: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _vehicle_rows(image_id: str) -> list[dict]:
    """Görüntünün araçları: güncel agent sonucu varsa onun seviyeleri, yoksa temel risk."""
    d = pipeline.build_dossier(image_id)
    by_id = {v.vehicle_id: v for v in d.vehicles}
    _, assessed, assessment = effective_risk(image_id)
    rows = []
    if assessed:
        for v in assessment["vehicles"]:
            ev = by_id.get(v["vehicle_id"])
            rows.append({"vehicle_id": v["vehicle_id"], "label": v["label"], "track_id": v["track_id"],
                         "risk_level": v["risk_level"], "baseline_level": v["baseline_level"],
                         "score": v["baseline_score"], "rationale": v["rationale"], "source": v["source"],
                         "ev": ev})
    else:
        for ev in d.vehicles:
            r = ev.baseline_risk
            rows.append({"vehicle_id": ev.vehicle_id, "label": ev.label, "track_id": ev.track_id,
                         "risk_level": r.level.value, "baseline_level": r.level.value, "score": r.score,
                         "rationale": "; ".join(f.detail for f in r.factors), "source": "baseline", "ev": ev})
    return rows


@bp.get("/alerts")
def alerts():
    ctx = get_context()
    min_risk = request.args.get("min_risk", "high")
    if min_risk not in LEVELS:
        raise ApiError(400, "bad_request", f"min_risk {LEVELS} içinden olmalı")
    items = []
    for img in ctx.repo.images():
        for row in _vehicle_rows(img.id):
            if level_rank(row["risk_level"]) > level_rank(min_risk):
                continue
            ev = row.pop("ev")
            k = ev.kinematics if ev else None
            items.append({
                **row, "image_id": img.id, "capture_time": img.capture_time, "zone": ev.zone if ev else None,
                "lat": ev.lat if ev else None, "lon": ev.lon if ev else None,
                "dist_to_base_m": ev.dist_to_base_m if ev else None,
                "eta_min": k.eta_min if k else None, "consistent_approach": k.consistent_approach if k else False,
                "circling": k.circling if k else False,
                "headline": row["rationale"].split(". ")[0][:200],
            })
    items.sort(key=lambda x: (level_rank(x["risk_level"]), -x["score"], x["capture_time"]))
    return jsonify({"total": len(items), "items": items})


@bp.get("/timeline")
def timeline():
    ctx = get_context()
    events = []
    for r in ctx.repo.reports():
        j = report_json(ctx, r.id)
        events.append({"time": r.time, "kind": "report", "id": r.id, "source": j["source"],
                       "category": j["category"], "status": j["status"], "text": r.text,
                       "image_ids": j["links"]["images"]})
    for img in ctx.repo.images():
        risk, assessed, _ = effective_risk(img.id)
        events.append({"time": img.capture_time, "kind": "capture", "id": img.id, "max_risk": risk,
                       "assessed": assessed})
        for row in _vehicle_rows(img.id):
            row.pop("ev")
            if level_rank(row["risk_level"]) <= level_rank("high"):
                events.append({"time": img.capture_time, "kind": "alert", "id": row["vehicle_id"],
                               "image_id": img.id, "risk_level": row["risk_level"], "label": row["label"]})
    kind_order = {"report": 0, "capture": 1, "alert": 2}
    events.sort(key=lambda e: (e["time"], kind_order[e["kind"]], e["id"]))
    return jsonify({"events": events})


@bp.post("/alert-rules/test")
def alert_rule_test():
    """Komutan alarm kuralı: {"text": "Bir kamyon üsse 1 km'den fazla yaklaşırsa uyar"} ya da {"rule": {...}}
    → metni LLM kurala çevirir (yoksa kural ayrıştırıcı), kural tüm gün üzerinde kodla geriye dönük sınanır."""
    from backend.engine.analysis.alert_rules import backtest, parse, rule_from_dict
    body = request.get_json(silent=True) or {}
    if isinstance(body.get("rule"), dict):
        rule, notes, text, parsed_by = rule_from_dict(body["rule"]), [], None, "yapılandırılmış"
    else:
        text = str(body.get("text") or "").strip()
        if not text:
            raise ApiError(400, "bad_request", "text ya da rule gerekli")
        rule, notes, parsed_by = parse(text)
    return jsonify({"text": text, "notes": notes, "parsed_by": parsed_by, **backtest(rule)})


@bp.post("/chat")
def chat():
    """Analist Asistanı: {"messages": [{"role","content"}], "context": {...}} → {"reply", "actions", "tools"}"""
    from backend.engine.chat import chat as run_chat
    from backend.engine.llm.client import BudgetExceeded, LLMUnavailable
    body = request.get_json(silent=True) or {}
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ApiError(400, "bad_request", "messages boş olamaz")
    try:
        return jsonify(run_chat(messages, body.get("context") or {}))
    except (LLMUnavailable, BudgetExceeded) as e:
        raise ApiError(503, "llm_unavailable", str(e))

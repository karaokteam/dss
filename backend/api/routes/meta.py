"""/health, /overview, /zones, /llm/budget, /config"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict

from flask import Blueprint, jsonify

from backend.api.serializers import LEVELS, image_summary
from backend.config import settings
from backend.engine.analysis.consistency import get_context

bp = Blueprint("meta", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "model": settings.llm.model, "llm_enabled": settings.llm.enabled})


@bp.get("/zones")
def zones():
    ctx = get_context()
    b = ctx.repo.base
    return jsonify({"base": {"name": b.name, "lat": b.lat, "lon": b.lon},
                    "zones": [{"name": z.name, "lat": z.lat, "lon": z.lon} for z in ctx.repo.zones]})


@bp.get("/overview")
def overview():
    ctx = get_context()
    repo = ctx.repo
    images = [image_summary(ctx, img) for img in repo.images()]
    risk = Counter(i["max_risk"] for i in images)
    times = [p.t for t in repo.tracks() for p in (t.points[0], t.last)] + [r.t for r in repo.reports()]
    from backend.engine.models import fmt_hhmm
    b = repo.base
    return jsonify({
        "base": {"name": b.name, "lat": b.lat, "lon": b.lon},
        "zones": [{"name": z.name, "lat": z.lat, "lon": z.lon} for z in repo.zones],
        "time_range": {"from": fmt_hhmm(min(times)), "to": fmt_hhmm(max(times))},
        "counts": {"images": len(images), "detections": len(repo.dataset.detections),
                   "tracks": len(repo.tracks()), "reports": len(repo.reports()),
                   "assessed": sum(i["assessed"] for i in images)},
        "risk_summary": {lvl: risk.get(lvl, 0) for lvl in LEVELS},
        "images": images,
    })


@bp.get("/llm/budget")
def budget():
    from backend.engine.llm.client import LLMUnavailable, get_client
    try:
        return jsonify(get_client().key_info())
    except LLMUnavailable as e:
        return jsonify({"error": {"code": "llm_unavailable", "message": str(e)}}), 503


@bp.get("/config")
def config():
    """Eşikler ve ağırlıklar (salt okunur; UI'da 'nasıl hesaplandı' paneli için)."""
    return jsonify({"match": asdict(settings.match), "kinematics": asdict(settings.kinematics),
                    "reports": asdict(settings.reports), "risk": asdict(settings.risk),
                    "agent": asdict(settings.agent),
                    "llm": {"model": settings.llm.model, "max_concurrency": settings.llm.max_concurrency,
                            "budget_stop_usd": settings.llm.budget_stop_usd}})

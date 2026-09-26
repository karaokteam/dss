"""Kural motoru: tüm kayıtlı kuralları çalıştırır, puanları toplar, seviyeyi belirler.

LLM çağrılmaz. Kurallar: agent/risk/rules/ (RSK-1..RSK-3). Eşikler: agent/config/risk.py (SON-2).
"""

import agent.risk.rules  # noqa: F401 — kuralları kaydeder
from agent import config
from agent.risk.registry import RULES, RuleContext
from agent.schemas import ClaimVerdict, GeoDetection, MotionProfile, RiskLevel, VehicleFinding


def level_for(score: float) -> RiskLevel:
    for level, floor in config.RISK_LEVELS.items():
        if score >= floor:
            return level
    return "LOW"


def score(
    geo: GeoDetection,
    track_id: str | None,
    motion: MotionProfile | None,
    verdicts: list[ClaimVerdict],
) -> VehicleFinding:
    ctx = RuleContext(geo=geo, track_id=track_id, motion=motion, verdicts=verdicts)
    factors = [f for r in RULES.values() if (f := r(ctx)) is not None]
    total = sum(f.points for f in factors)
    return VehicleFinding(
        geo=geo,
        track_id=track_id,
        motion=motion,
        verdicts=verdicts,
        score=total,
        level=level_for(total),
        factors=factors,
    )

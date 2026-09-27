"""Kural tabanlı temel risk skoru (0–100) ve seviyesi.

Her katkı ayrı bir `RiskFactor` olarak açıklanır; agent bu faktörleri görür ve gerekçesiyle skordan sapabilir.
Ağırlık ve eşikler config.risk'tedir (Step 6 sonunda elle inceleme ile kalibre edilir).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.config import settings
from backend.engine.models import (
    BaselineRisk, ClaimCheck, ClaimStatus, ClaimType, Kinematics, RiskFactor, RiskLevel,
)

HEAVY = {"truck", "bus"}


@dataclass(frozen=True)
class RiskInput:
    label: str | None
    confidence: float | None
    has_track: bool
    dist_to_base_m: float
    kinematics: Kinematics | None
    claims: tuple[ClaimCheck, ...]
    heavy_group_size: int = 0        # aynı görüntüde bu aracın yakınındaki ağır araç sayısı (kendisi dahil)


def level_for(score: int) -> RiskLevel:
    cfg = settings.risk
    if score >= cfg.critical_at:
        return RiskLevel.CRITICAL
    if score >= cfg.high_at:
        return RiskLevel.HIGH
    if score >= cfg.medium_at:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def score(inp: RiskInput) -> BaselineRisk:
    cfg, w = settings.risk, settings.risk.weights
    factors: list[RiskFactor] = []

    def add(name: str, detail: str) -> None:
        factors.append(RiskFactor(name=name, weight=w[name], detail=detail))

    # ---- konum
    d = inp.dist_to_base_m
    if d < cfg.near_base_m:
        add("near_base", f"üsse {d:.0f} m")
    elif d < cfg.mid_base_m:
        add("mid_base", f"üsse {d:.0f} m")

    # ---- tip
    if inp.label in HEAVY:
        add("heavy_vehicle", f"ağır araç ({inp.label})")
    if inp.label in HEAVY and inp.heavy_group_size >= cfg.group_min:
        add("group", f"{cfg.group_radius_m:.0f} m içinde {inp.heavy_group_size} ağır araç")

    # ---- hareket
    k = inp.kinematics
    if k is not None:
        rc = k.radial_change_window_m
        if k.consistent_approach:
            add("consistent_approach", f"2 saatte {k.moves} hareketin hepsi üsse yaklaştırdı "
                                       f"({k.dist_to_base_start_m:.0f} → {k.dist_to_base_m:.0f} m)")
        if k.motion == "approaching":
            add("approaching", f"son {settings.kinematics.radial_window_min} dk'da üsse {-rc:.0f} m yaklaştı")
            if rc is not None and rc <= -cfg.fast_approach_m:
                add("fast_approach", f"{-rc:.0f} m ≥ {cfg.fast_approach_m:.0f} m")
        if k.eta_min is not None and k.eta_min <= cfg.short_eta_min:
            add("short_eta", f"tahmini varış {k.eta_min:.0f} dk")
        if k.motion == "receding":
            add("receding", f"son {settings.kinematics.radial_window_min} dk'da üsten {rc:.0f} m uzaklaştı")
        if k.stationary_min >= cfg.long_stationary_min and d < cfg.mid_base_m:
            add("long_stationary_near_base", f"{k.stationary_min} dk durağan, üsse {d:.0f} m")
        if (k.tortuosity is not None and k.tortuosity >= cfg.loiter_tortuosity
                and k.moves >= cfg.loiter_min_moves):
            add("loitering", f"dolaşma: yol/yer değiştirme {k.tortuosity:.1f}, {k.moves} hareket")

    # ---- raporlar
    non_identity = [c for c in inp.claims if c.claim_type != ClaimType.IDENTITY]
    identity = [c for c in inp.claims if c.claim_type == ClaimType.IDENTITY]
    contradicted = [c for c in inp.claims if c.status == ClaimStatus.CONTRADICTED]
    partial = [c for c in non_identity if c.status == ClaimStatus.PARTIAL]
    if contradicted:
        add("report_contradiction", "çelişen rapor: " + ", ".join(sorted({c.report_id for c in contradicted})))
    elif partial:
        add("report_partial_contradiction", "kısmen tutan rapor: " + ", ".join(sorted({c.report_id for c in partial})))
    if any(c.status == ClaimStatus.CONTRADICTED for c in identity):
        add("unverified_friendly_claim", "dost/ikmal iddiası gözlemle çelişiyor: "
            + ", ".join(sorted({c.report_id for c in identity if c.status == ClaimStatus.CONTRADICTED})))
    elif identity and all(c.status == ClaimStatus.VERIFIED for c in identity):
        add("verified_friendly_claim", "dost iddiası fiziksel olarak tutarlı: "
            + ", ".join(sorted({c.report_id for c in identity})))

    # ---- tespit güveni
    if not inp.has_track and inp.confidence is not None and inp.confidence < settings.match.low_confidence:
        add("low_confidence", f"track'siz ve düşük güvenli tespit ({inp.confidence:.2f})")

    total = max(0, min(100, sum(f.weight for f in factors)))
    return BaselineRisk(score=total, level=level_for(total), factors=tuple(factors))

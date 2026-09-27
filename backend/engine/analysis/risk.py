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


def _is_reassuring(c: ClaimCheck) -> bool:
    """Riski düşürmeye yönelik iddia: dost/ikmal kimliği ya da "olağan" / "uzaklaşıyor" hareketi."""
    if c.claim_type == ClaimType.IDENTITY:
        return True
    return c.claim_type == ClaimType.MOTION and (c.observed or {}).get("claimed_motion") in ("leaving_area",
                                                                                          "normal_activity")


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
        if k.circling:
            add("circling_base", f"üssün etrafında {k.circling_radius_m:.0f} m yarıçapta döndü ({k.circling_window}, "
                                 f"{k.circling_sweep_deg:.0f}° tarama)")
        elif k.min_dist_to_base_m < settings.kinematics.close_pass_m and k.min_dist_to_base_m < d - 200:
            add("close_pass", f"kayıt içinde üsse {k.min_dist_to_base_m:.0f} m'ye kadar yaklaştı")
        if (k.tortuosity is not None and k.tortuosity >= cfg.loiter_tortuosity
                and k.moves >= cfg.loiter_min_moves):
            add("loitering", f"dolaşma: yol/yer değiştirme {k.tortuosity:.1f}, {k.moves} hareket")

    # ---- raporlar: yalnızca riski DÜŞÜRMEYE yönelik iddialar (dost / "olağan" / "uzaklaşıyor") risk etkiler.
    # Gözlemle çelişirlerse ya da üsse yaklaşan araca iliştirilmişlerse şüphe sinyalidir. Hiçbir iddia riski düşürmez;
    # yanlış bir tehdit iddiası (ör. şişirilmiş kamyon sayısı) aracın riskini artırmaz.
    misleading = sorted({c.report_id for c in inp.claims if _is_reassuring(c) and (
        c.status == ClaimStatus.CONTRADICTED or (c.observed or {}).get("reassuring_on_approach"))})
    if misleading:
        add("reassuring_claim", "güven verici iddia gözlemle çelişiyor ya da üsse yaklaşan araca iliştirilmiş: "
            + ", ".join(misleading))

    # ---- tespit güveni
    if not inp.has_track and inp.confidence is not None and inp.confidence < settings.match.low_confidence:
        add("low_confidence", f"track'siz ve düşük güvenli tespit ({inp.confidence:.2f})")

    total = max(0, min(100, sum(f.weight for f in factors)))
    return BaselineRisk(score=total, level=level_for(total), factors=tuple(factors))

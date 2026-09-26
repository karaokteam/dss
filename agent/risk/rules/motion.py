"""Hareket kuralları. Görev: RSK-2"""

from agent.risk.registry import RuleContext, rule
from agent.schemas import RiskFactor


@rule
def approaching_base(ctx: RuleContext) -> RiskFactor | None:
    """Üsse yaklaşıyor + ETA kısa → puan. motion None ise (eşleşmeyen araç) OI-RSK-2 kararına göre."""
    return None  # TODO(RSK-2)


@rule
def loitering(ctx: RuleContext) -> RiskFactor | None:
    """Uzun süre duraklama / bölgede dolaşma → puan."""
    return None  # TODO(RSK-2)

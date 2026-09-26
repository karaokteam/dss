"""Rapor kuralları. Görev: RSK-3 · Açık konu: OI-RAP-1

İlke: doğrulanmamış veya güven verici (de_escalate) iddia skoru ASLA düşürmez.
Doğrulanmış tehdit iddiası puan ekleyebilir; çelişen iddia brief'te belirtilir, puan eklemez.
"""

from agent.risk.registry import RuleContext, rule
from agent.schemas import RiskFactor


@rule
def confirmed_threat_report(ctx: RuleContext) -> RiskFactor | None:
    return None  # TODO(RSK-3)

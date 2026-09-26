"""Konum kuralları. Görev: RSK-1

Kural yazılana kadar None döner → pipeline çalışmaya devam eder.
"""

from agent.risk.registry import RuleContext, rule
from agent.schemas import RiskFactor


@rule
def near_base(ctx: RuleContext) -> RiskFactor | None:
    """Üsse DISTANCE_CRITICAL_M'den yakın → puan. Sınıf (truck/bus) ağırlığı da burada olabilir."""
    return None  # TODO(RSK-1)

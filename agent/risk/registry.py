"""Kural kaydı. Yeni kural: rules/ altındaki bir dosyaya `@rule` ile fonksiyon ekle — başka yere dokunma."""

from collections.abc import Callable
from dataclasses import dataclass, field

from agent.schemas import ClaimVerdict, GeoDetection, MotionProfile, RiskFactor


@dataclass(frozen=True)
class RuleContext:
    geo: GeoDetection
    track_id: str | None
    motion: MotionProfile | None
    verdicts: list[ClaimVerdict] = field(default_factory=list)


Rule = Callable[[RuleContext], RiskFactor | None]
RULES: dict[str, Rule] = {}


def rule(fn: Rule) -> Rule:
    RULES[f"{fn.__module__.rsplit('.', 1)[-1]}.{fn.__name__}"] = fn
    return fn

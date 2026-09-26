"""AKIŞ 04b."""

from pydantic import BaseModel, Field

from agent.schemas.common import RiskLevel
from agent.schemas.geo import GeoDetection
from agent.schemas.reports import ClaimVerdict
from agent.schemas.tracks import MotionProfile


class RiskFactor(BaseModel):
    name: str
    points: float
    reason: str


class VehicleFinding(BaseModel):
    geo: GeoDetection
    track_id: str | None
    motion: MotionProfile | None
    verdicts: list[ClaimVerdict] = Field(default_factory=list)
    score: float
    level: RiskLevel
    factors: list[RiskFactor]  # her puanın gerekçesi — tasarım ilkesi 3

"""AKIŞ 04a."""

from typing import Literal

from pydantic import BaseModel

from agent.schemas.common import LatLon, VehicleClass

ClaimIntent = Literal["escalate", "de_escalate", "neutral", "irrelevant"]


class ReportClaim(BaseModel):
    report_id: str
    time: str
    source: str
    vehicle_class: VehicleClass | None = None
    count: int | None = None
    location: LatLon | None = None
    zone: str | None = None
    intent: ClaimIntent = "neutral"
    extracted_by: Literal["regex", "llm"] = "regex"


class ClaimVerdict(BaseModel):
    claim: ReportClaim
    status: Literal["confirmed", "contradicted", "unverifiable", "irrelevant"]
    evidence: str  # insan-okur gerekçe
    track_id: str | None = None
    detection_index: int | None = None

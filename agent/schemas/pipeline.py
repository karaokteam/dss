"""Pipeline çıktıları."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.schemas.common import RiskLevel
from agent.schemas.inputs import ImageMeta
from agent.schemas.reports import ClaimVerdict
from agent.schemas.risk import VehicleFinding


class Brief(BaseModel):
    image_id: str
    level: RiskLevel  # risk/'ten gelir, LLM değiştirmez
    text: str
    model: str | None = None  # None → LLM'siz şablon


class ImageAssessment(BaseModel):
    image_id: str
    meta: ImageMeta
    findings: list[VehicleFinding]
    overall_level: RiskLevel
    report_verdicts: list[ClaimVerdict] = Field(default_factory=list)  # araca bağlanamayanlar dahil
    brief: Brief | None = None


class PipelineEvent(BaseModel):
    step: int  # 1..8, README "Pipeline"
    name: str
    status: Literal["start", "done", "error"]
    payload: dict[str, Any] = Field(default_factory=dict)

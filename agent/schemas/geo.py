"""AKIŞ 02."""

from pydantic import BaseModel

from agent.schemas.detection import Detection


class GeoDetection(BaseModel):
    detection: Detection
    lat: float
    lon: float
    distance_to_base_m: float
    nearest_zone: str | None = None

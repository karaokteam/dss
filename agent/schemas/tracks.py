"""AKIŞ 03."""

from pydantic import BaseModel, Field


class TrackMatch(BaseModel):
    detection_index: int  # locate() çıktısındaki sıra
    track_id: str | None  # None → eşleşmedi (OI-RSK-2)
    distance_m: float | None = None


class MotionProfile(BaseModel):
    track_id: str
    speed_mps: float
    heading_deg: float  # 0 = kuzey, saat yönü
    approaching_base: bool
    closing_speed_mps: float  # + → üsse yaklaşıyor
    stopped_minutes: int
    eta_min: float | None  # yaklaşmıyorsa None
    zones_visited: list[str] = Field(default_factory=list)

"""AKIŞ 01. Kutular Kaggle formatında: (x, y) sol-üst köşe, (w, h) piksel."""

from pydantic import BaseModel

from agent.schemas.common import VehicleClass


class Detection(BaseModel):
    image_id: str
    cls: VehicleClass
    confidence: float
    x: float
    y: float
    w: float
    h: float

    @property
    def center_px(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2

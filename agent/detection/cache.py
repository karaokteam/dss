"""Tespit sonuçları için JSON cache (cache/detections/<image_id>.json). Görev: DET-3"""

from agent.schemas import Detection


def read(image_id: str) -> list[Detection] | None:
    raise NotImplementedError


def write(image_id: str, detections: list[Detection]) -> None:
    raise NotImplementedError

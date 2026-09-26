"""YOLO sarmalayıcı. Görev: DET-2 · Açık konu: OI-DET-1

Önce cache'e bakar; yoksa modeli çalıştırır ve cache'e yazar.
MIN_BOX_AREA_PX2 altındaki kutular atılır.
"""

from agent.schemas import Detection


def detect(image_id: str, use_cache: bool = True) -> list[Detection]:
    raise NotImplementedError

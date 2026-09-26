"""Veri varsayım kontrolleri. Görev: GEO-1 · Karar: PROGRESS → GEO"""

from agent.schemas import ImageMeta


def check_north_up(meta: ImageMeta, tol: float = 1e-6) -> bool:
    """Üst köşeler aynı enlemde, sol köşeler aynı boylamda mı?"""
    raise NotImplementedError

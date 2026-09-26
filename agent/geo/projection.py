"""Piksel → lat/lon. Görev: GEO-1 · Karar: PROGRESS → GEO"""

from agent.schemas import ImageMeta, LatLon


def pixel_to_latlon(px: float, py: float, meta: ImageMeta) -> LatLon:
    raise NotImplementedError

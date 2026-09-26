"""Tespitleri haritaya yerleştirir. Görev: GEO-2"""

from agent.schemas import Detection, GeoDetection, ImageMeta, ZonesFile


def locate(detections: list[Detection], meta: ImageMeta, zones: ZonesFile) -> list[GeoDetection]:
    """projection.pixel_to_latlon + spatial.distance_m (üsse) + spatial.nearest_zone."""
    raise NotImplementedError

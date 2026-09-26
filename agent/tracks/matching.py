"""Tespit ↔ track Hungarian eşleştirme. Görev: TRK-1 · Açık konular: OI-TRK-2, OI-RSK-2"""

from agent.schemas import GeoDetection, TrackMatch, TrackPoint


def match(geo_dets: list[GeoDetection], tracks: list[TrackPoint], capture_time: str) -> list[TrackMatch]:
    """timeline.positions_at + spatial.distance_m ile maliyet matrisi → scipy linear_sum_assignment.
    MATCH_MAX_DIST_M üstü → track_id=None. Her tespit için bir TrackMatch (detection_index sırasıyla)."""
    raise NotImplementedError

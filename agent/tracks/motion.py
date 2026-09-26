"""Hız · yön · duraklama · üsse yaklaşma · ETA. Görev: TRK-2 · Açık konu: OI-RSK-1"""

from agent.schemas import MotionProfile, TrackPoint, ZonesFile


def analyze(track_id: str, tracks: list[TrackPoint], capture_time: str, zones: ZonesFile) -> MotionProfile:
    """timeline.series(until=capture_time) + spatial.distance_m / bearing_deg.
    Üs konumu zones.base'den. ETA kuş uçuşu mesafe / yaklaşma hızı."""
    raise NotImplementedError

"""Harita bileşeni: üs, bölgeler, görüntü karesi, tespitler, track izleri. Görev: UI-1

Diğer sekmeler sadece render_map(...) çağırır.
"""

from agent.schemas import ImageAssessment, TrackPoint, ZonesFile


def render_map(
    zones: ZonesFile, assessment: ImageAssessment | None = None, tracks: list[TrackPoint] | None = None
) -> None:
    raise NotImplementedError

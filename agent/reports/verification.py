"""İddiaları tespit + track kanıtıyla karşılaştırır. Görev: RAP-3 · Açık konu: OI-RAP-1

Doğrulanamayan iddia 'unverifiable' olur ve skoru düşürmez.
"""

from agent.schemas import ClaimVerdict, GeoDetection, ImageMeta, ReportClaim, TrackPoint


def verify(
    claims: list[ReportClaim],
    geo_dets: list[GeoDetection],
    meta: ImageMeta,
    tracks: list[TrackPoint],
) -> list[ClaimVerdict]:
    raise NotImplementedError

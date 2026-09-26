"""Track zaman serisi yardımcıları — HAZIR (Step 0).

Tolerans config.MATCH_TIME_TOLERANCE_MIN'den gelir (karar: 0, track'ler çekim anında biter).
"""

from itertools import groupby

from agent import config
from agent.schemas import TrackPoint, hhmm_to_min


def series(tracks: list[TrackPoint], track_id: str, until: str | None = None) -> list[TrackPoint]:
    """Tek track'in zamana göre sıralı noktaları (until dahil)."""
    pts = [p for p in tracks if p.track_id == track_id]
    if until is not None:
        pts = [p for p in pts if hhmm_to_min(p.time) <= hhmm_to_min(until)]
    return sorted(pts, key=lambda p: hhmm_to_min(p.time))


def positions_at(
    tracks: list[TrackPoint], time: str, tolerance_min: int | None = None
) -> dict[str, TrackPoint]:
    """Verilen andaki track konumları: tam eşleşme → iki nokta arası doğrusal enterpolasyon →
    tolerans içindeki en yakın nokta. Hiçbiri yoksa o track dönmez."""
    tol = config.MATCH_TIME_TOLERANCE_MIN if tolerance_min is None else tolerance_min
    t = hhmm_to_min(time)
    out: dict[str, TrackPoint] = {}
    key = lambda p: p.track_id  # noqa: E731
    for track_id, group in groupby(sorted(tracks, key=key), key=key):
        pts = sorted(group, key=lambda p: hhmm_to_min(p.time))
        before = [p for p in pts if hhmm_to_min(p.time) <= t]
        after = [p for p in pts if hhmm_to_min(p.time) >= t]
        if before and after:
            a, b = before[-1], after[0]
            ta, tb = hhmm_to_min(a.time), hhmm_to_min(b.time)
            k = 0.0 if tb == ta else (t - ta) / (tb - ta)
            out[track_id] = TrackPoint(
                track_id=track_id, time=time, lat=a.lat + k * (b.lat - a.lat), lon=a.lon + k * (b.lon - a.lon)
            )
            continue
        nearest = min(pts, key=lambda p: abs(hhmm_to_min(p.time) - t))
        if abs(hhmm_to_min(nearest.time) - t) <= tol:
            out[track_id] = nearest
    return out

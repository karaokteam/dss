"""Çekim anında tespit ↔ track birebir eşleştirmesi.

Hangi track'in hangi araca ait olduğu verilmez. Track'in son noktası = görüntüdeki konum olduğundan,
çekim saatinde biten track'ler tespitlerle mesafeye göre birebir (Hungarian) eşleştirilir.
Yan yana araçlarda "en yakını seç" aynı track'i birden fazla araca bağlayacağı için birebir atama şarttır.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from backend.config import settings
from backend.engine.data.repository import Repository
from backend.engine.geo.geometry import distance_m, distance_to_footprint_m, in_footprint
from backend.engine.models import ImageMatch, Match, UnmatchedTrack

_UNREACHABLE = 1e9


def match_image(repo: Repository, image_id: str, gate_m: float | None = None) -> ImageMatch:
    gate = settings.match.gate_m if gate_m is None else gate_m
    image = repo.image(image_id)
    detections = repo.detections_for(image_id)
    # Aynı saatte çekilmiş başka görüntünün track'leri bu görüntüye karışmasın
    tracks = [t for t in repo.tracks_ending_at(image.capture_min) if t.image_id in (image_id, None)]

    cost = np.full((len(detections), len(tracks)), _UNREACHABLE)
    for i, d in enumerate(detections):
        for j, t in enumerate(tracks):
            dist = distance_m(d.lat, d.lon, t.last.lat, t.last.lon)
            if dist <= gate:
                cost[i, j] = dist

    matches: list[Match] = []
    matched_dets, matched_tracks = set(), set()
    if detections and tracks:
        rows, cols = linear_sum_assignment(cost)
        for i, j in zip(rows, cols):
            if cost[i, j] >= _UNREACHABLE:
                continue
            margin = cost[i, j] + settings.match.ambiguity_margin_m
            alternatives = tuple(tracks[k].id for k in range(len(tracks))
                                 if k != j and cost[i, k] <= margin)
            matches.append(Match(detection_id=detections[i].id, track_id=tracks[j].id,
                                 dist_m=round(float(cost[i, j]), 2), alternatives=alternatives))
            matched_dets.add(i)
            matched_tracks.add(j)

    unmatched_tracks = tuple(
        UnmatchedTrack(track_id=t.id,
                       in_frame=in_footprint(image, t.last.lat, t.last.lon),
                       dist_to_footprint_m=round(distance_to_footprint_m(image, t.last.lat, t.last.lon), 1))
        for j, t in enumerate(tracks) if j not in matched_tracks)

    return ImageMatch(
        image_id=image_id,
        matches=tuple(sorted(matches, key=lambda m: m.detection_id)),
        unmatched_detections=tuple(d.id for i, d in enumerate(detections) if i not in matched_dets),
        unmatched_tracks=unmatched_tracks,
    )


def match_all(repo: Repository, gate_m: float | None = None) -> dict[str, ImageMatch]:
    return {img.id: match_image(repo, img.id, gate_m) for img in repo.images()}

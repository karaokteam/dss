"""Raporları görüntülere, track'lere, tespitlere ve bölgelere bağlar.

- Koordinatlı rapor: koordinat, anlatılan aracın GÖRÜNTÜDEKİ konumudur (veri: 5 ondalıklı koordinatların 31/35'i
  görüntüdeki araca ≤3 m; görev tanımındaki örnek de böyle eşleştirir). Görüntü: rapordan sonraki 2 saat içinde
  çekilmiş ve ayak izi koordinata yakın olan; track'ler: o görüntüde biten ve SON (çekim) noktası koordinata yakın olanlar.
  İddianın doğruluğu ise aracın rapordan önceki davranışıyla ölçülür (analysis/consistency.py).
- Bölge raporu: o bölgedeki görüntüler ve rapor saatinde o bölgede kaydı olan track'ler bağlam olarak bağlanır.
- Genel rapor (hava, tatbikat vb.): bağlantı yok.
"""

from __future__ import annotations

from backend.config import settings
from backend.engine.data.repository import Repository
from backend.engine.geo.geometry import distance_m, distance_to_footprint_m
from backend.engine.geo.zones import nearest_zone
from backend.engine.models import (
    Claim, DetectionLink, ImageLink, Report, ReportLinks, TrackLink,
)


def link_report(repo: Repository, report: Report, claim: Claim) -> ReportLinks:
    cfg = settings.reports
    if claim.lat is not None and claim.lon is not None:
        return _link_coordinate(repo, report, claim, cfg)
    if claim.zone:
        return _link_zone(repo, report, claim.zone, cfg)
    return ReportLinks(report_id=report.id, zone=None)


def link_all(repo: Repository, claims: dict[str, Claim]) -> dict[str, ReportLinks]:
    return {r.id: link_report(repo, r, claims[r.id]) for r in repo.reports() if r.id in claims}


def _in_window(capture_min: int, report_min: int, window_min: int) -> bool:
    return 0 <= capture_min - report_min <= window_min


def _link_coordinate(repo: Repository, report: Report, claim: Claim, cfg) -> ReportLinks:
    lat, lon = claim.lat, claim.lon
    zone = claim.zone or nearest_zone(lat, lon, repo.zones)[0].name

    images = []
    for img in repo.images():
        if not _in_window(img.capture_min, report.t, cfg.window_min):
            continue
        d = distance_to_footprint_m(img, lat, lon)
        if d <= cfg.link_radius_m:
            images.append(ImageLink(image_id=img.id, dist_to_footprint_m=round(d, 1),
                                    minutes_before_capture=img.capture_min - report.t))
    images.sort(key=lambda x: (x.dist_to_footprint_m, x.minutes_before_capture))

    image_ids = {il.image_id for il in images}
    candidates = sorted((distance_m(lat, lon, tr.last.lat, tr.last.lon), tr) for tr in repo.tracks()
                        if tr.image_id in image_ids)
    nearest = round(candidates[0][0], 1) if candidates else None
    tracks = tuple(TrackLink(track_id=tr.id, dist_m=round(d, 1), image_id=tr.image_id)
                   for d, tr in candidates if d <= cfg.track_link_radius_m)

    detections = []
    for link in images:
        for det in repo.detections_for(link.image_id):
            d = distance_m(lat, lon, det.lat, det.lon)
            if d <= cfg.track_link_radius_m:
                detections.append(DetectionLink(detection_id=det.id, image_id=det.image_id,
                                                label=det.label, dist_m=round(d, 1)))
    detections.sort(key=lambda x: x.dist_m)

    return ReportLinks(report_id=report.id, zone=zone, images=tuple(images), tracks=tracks,
                       detections=tuple(detections), nearest_track_m=nearest)


def _link_zone(repo: Repository, report: Report, zone: str, cfg) -> ReportLinks:
    images = []
    for img in repo.images():
        if not _in_window(img.capture_min, report.t, cfg.window_min):
            continue
        if nearest_zone(*img.center, repo.zones)[0].name == zone:
            images.append(ImageLink(image_id=img.id, dist_to_footprint_m=0.0,
                                    minutes_before_capture=img.capture_min - report.t))
    zone_tracks = tuple(tr.id for tr, p in repo.tracks_active_at(report.t)
                        if nearest_zone(p.lat, p.lon, repo.zones)[0].name == zone)
    return ReportLinks(report_id=report.id, zone=zone, images=tuple(images), zone_tracks=zone_tracks)

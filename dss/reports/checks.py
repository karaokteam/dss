"""
Sahibi : Kişi 4
Görev  : Koordinatlı raporlar için objektif kontroller (yakın track, yakın tespit, hareketsizlik)

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    checks_for(report, detections, capture_time, D) -> dss.schemas.ReportChecks

Hüküm vermez, yalnızca ölçer. Alan anlamları schemas.ReportChecks ile aynıdır:
  tracks_near_at_report_time : rapor saatinde (±5 dk) rapor noktasına <= 150 m track'ler, yakından uzağa
  detections_near            : çekim anında rapor noktasına <= 150 m tespitler
  stationary_tracks_near     : bu track'lerden rapor saatine kadar >= 30 dk yerinden kıpırdamayanlar
  label_counts_near          : detections_near'ın sınıf sayımı
Rapora özgü ek gerçekler (hedef araç, zaman kayması, süre kapsamı) için bkz. trace.py.
"""
import math
from typing import TYPE_CHECKING

import numpy as np

from dss.reports.claims import hm
from dss.schemas import DetectionEv, NearDetection, NearTrack, ReportChecks, ReportEv

if TYPE_CHECKING:
    from dss.evidence.builder import Data

CHECK_RADIUS_M = 150
REPORT_TIME_TOL_MIN = 5
STATIONARY_MIN = 30
STATIONARY_MAX_MOVE_M = 25


def checks_for(report: ReportEv, detections: list[DetectionEv], capture_time: str, D: "Data") -> ReportChecks:
    if report.lat is None or report.lon is None:
        raise ValueError(f"{report.report_id}: checks yalnızca koordinatlı raporlar için hesaplanır")
    x, y = D.xy(report.lat, report.lon)
    rt = hm(report.time)

    near_t = D.tracks[(D.tracks.t - rt).abs() <= REPORT_TIME_TOL_MIN]
    dv = np.hypot(near_t.x - x, near_t.y - y)
    best = dv[dv <= CHECK_RADIUS_M].groupby(near_t.track_id).min().sort_values()

    det_near = []
    for d in detections:
        dx, dy = D.xy(d.lat, d.lon)
        dist = math.hypot(dx - x, dy - y)
        if dist <= CHECK_RADIUS_M:
            det_near.append(NearDetection(det_id=d.det_id, label=d.label, dist_m=int(dist),
                                          has_track=d.track_id is not None))
    det_near.sort(key=lambda n: n.dist_m)

    stationary = []
    for tid in best.index:
        w = D.tracks[(D.tracks.track_id == tid) & D.tracks.t.between(rt - STATIONARY_MIN, rt)]
        if len(w) >= STATIONARY_MIN // 5 + 1 and \
                np.hypot(w.x - w.x.iloc[-1], w.y - w.y.iloc[-1]).max() < STATIONARY_MAX_MOVE_M:
            stationary.append(tid)

    counts: dict[str, int] = {}
    for n in det_near:
        counts[n.label] = counts.get(n.label, 0) + 1

    return ReportChecks(
        tracks_near_at_report_time=[NearTrack(track_id=t, dist_m=int(v)) for t, v in best.items()],
        detections_near=det_near, stationary_tracks_near=stationary, label_counts_near=counts)

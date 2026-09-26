"""
Sahibi : Kişi 4
Görev  : Raporun anlattığı aracı bul ve rapor anından çekim anına kadar izle

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    trace_for(report, detections, image_id, D) -> ReportTrace

Neden: 5 haneli koordinatlar görüntüdeki bir tespitin 0-1 m yakınına düşüyor; rapor belirli bir
aracı anlatıyor. O aracın track'i üzerinden iddia, rapor anındaki gerçek hareketle ölçülebilir.
Rapor noktasında rapor anında duran araçlar çekim anına kadar izlenir: yerinde mi, ayrıldı mı,
çekimde ne olarak tespit edildi? (RAPOR_DOGRULAMA.md B6-B8)

Hüküm vermez, yalnızca ölçer. ReportTrace şemada henüz yok: Kişi 5 onaylarsa
schemas.ReportChecks'e `trace` alanı olarak eklenecek (öneri: docs/SCHEMA_PROPOSAL_REPORTS.md).
"""
import math
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from dss.reports.claims import Claim, hm, parse_claim
from dss.schemas import DetectionEv, ReportEv, VehicleClass

if TYPE_CHECKING:
    from dss.evidence.builder import Data

LINK_RADIUS_M = {5: 10, 4: 30}   # koordinat hanesine göre hedef araç yarıçapı
FOLLOW_RADIUS_M = 75             # rapor anında noktadaki araçlar
FOLLOW_MAX = 3


class FollowedTrack(BaseModel):
    """Rapor anında rapor noktasında olan bir track'in çekim anındaki durumu."""
    track_id: str
    dist_at_report_m: int
    moved_until_capture_m: Optional[int] = None      # None: track çekim anını kapsamıyor
    in_frame_at_capture: Optional[bool] = None
    det_at_capture: Optional[str] = None             # çekimde bu track'e eşleşen tespit
    label_at_capture: Optional[VehicleClass] = None


class ReportTrace(BaseModel):
    """Rapora özgü ölçümler. Tüm sayılar koddan gelir."""
    target_det: Optional[str] = None                 # rapor noktasındaki tespit (çekim anı)
    target_track: Optional[str] = None               # hedef aracın track'i (tespit yoksa çekimdeki track konumu)
    target_link_m: Optional[int] = None
    target_dist_at_report_m: Optional[int] = None    # hedef araç rapor anında rapor noktasına ne kadar uzak
    target_moved_30m_before_report_m: Optional[int] = None
    target_approach_30m_before_report_m: Optional[int] = None   # + ise üsse yaklaşıyordu
    target_moved_report_to_capture_m: Optional[int] = None
    target_approach_report_to_capture_m: Optional[int] = None   # + ise rapordan sonra üsse yaklaştı
    claimed_duration_min: Optional[int] = None       # metindeki süre ("uzun süredir" = 60)
    duration_covered_min: Optional[int] = None       # bu sürenin track verisiyle kapsanan kısmı
    duration_max_move_m: Optional[int] = None        # kapsanan sürede en büyük yer değiştirme
    followed_tracks: list[FollowedTrack] = []


def _series(D: "Data", tid: str) -> dict[int, tuple[float, float, float]]:
    tr = D.tracks[D.tracks.track_id == tid]
    return {int(t): (float(x), float(y), float(d)) for t, x, y, d in zip(tr.t, tr.x, tr.y, tr.d, strict=True)}


def _in_frame(D: "Data", image_id: str, x: float, y: float) -> bool:
    c = D.meta[image_id]["corner_coordinates"]
    x0, y1 = D.xy(*c["top_left"])
    x1, y0 = D.xy(*c["bottom_right"])
    return x0 <= x <= x1 and y0 <= y <= y1


def trace_for(report: ReportEv, detections: list[DetectionEv], image_id: str, D: "Data",
              claim: Claim | None = None) -> ReportTrace:
    if report.lat is None or report.lon is None:
        raise ValueError(f"{report.report_id}: trace yalnızca koordinatlı raporlar için hesaplanır")
    claim = claim or parse_claim(report.text, D.zones)
    px, py = D.xy(report.lat, report.lon)
    rt, cap = hm(report.time), hm(D.meta[image_id]["capture_time"])
    out = ReportTrace(claimed_duration_min=claim.duration_min)

    # 1) Hedef araç: çekim anında rapor noktasına en yakın araç. Track konumları tespitten
    #    daha hassas (eşleşmelerin yarısı 0,2 m içinde) ve eşik altında kalan tespitleri de kapsar.
    radius = LINK_RADIUS_M.get(claim.coord_decimals or 4, LINK_RADIUS_M[4])
    det_of_track = {d.track_id: d for d in detections if d.track_id}
    cands = [(math.hypot(dx - px, dy - py), d.track_id, d)
             for d in detections for dx, dy in [D.xy(d.lat, d.lon)]]
    at_cap = D.tracks[D.tracks.t == cap]
    cands += [(math.hypot(x - px, y - py), tid, det_of_track.get(tid))
              for tid, x, y in zip(at_cap.track_id, at_cap.x, at_cap.y, strict=True)]
    cands = [c for c in cands if c[0] <= radius]
    if cands:
        dist, tid, det = min(cands, key=lambda c: c[0])
        out.target_det, out.target_track, out.target_link_m = det.det_id if det else None, tid, int(dist)

    # 2) Hedef aracın rapor anındaki durumu
    if out.target_track:
        s = _series(D, out.target_track)
        if rt in s:
            x, y, d = s[rt]
            out.target_dist_at_report_m = int(math.hypot(x - px, y - py))
            if rt - 30 in s:
                x0, y0, d0 = s[rt - 30]
                out.target_moved_30m_before_report_m = int(math.hypot(x - x0, y - y0))
                out.target_approach_30m_before_report_m = int(d0 - d)
            if cap in s:
                out.target_moved_report_to_capture_m = int(math.hypot(s[cap][0] - x, s[cap][1] - y))
                out.target_approach_report_to_capture_m = int(d - s[cap][2])
            if claim.duration_min:
                start = max(rt - claim.duration_min, min(s))
                out.duration_covered_min = rt - start
                out.duration_max_move_m = int(max(math.hypot(s[t][0] - x, s[t][1] - y)
                                                  for t in s if start <= t <= rt))

    # 3) Rapor anında noktada olan track'ler çekim anına kadar
    at_rt = D.tracks[D.tracks.t == rt]
    dd = ((at_rt.x - px) ** 2 + (at_rt.y - py) ** 2) ** 0.5
    for i in dd[dd <= FOLLOW_RADIUS_M].sort_values().index[:FOLLOW_MAX]:
        tid = at_rt.loc[i, "track_id"]
        s = _series(D, tid)
        f = FollowedTrack(track_id=tid, dist_at_report_m=int(dd[i]))
        if cap in s:
            f.moved_until_capture_m = int(math.hypot(s[cap][0] - s[rt][0], s[cap][1] - s[rt][1]))
            f.in_frame_at_capture = _in_frame(D, image_id, s[cap][0], s[cap][1])
            if det := det_of_track.get(tid):
                f.det_at_capture, f.label_at_capture = det.det_id, det.label
        out.followed_tracks.append(f)
    return out

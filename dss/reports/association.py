"""
Sahibi : Kişi 4
Görev  : Rapor <-> görüntü ilişkilendirme (koordinat / bölge / genel)

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    reports_for(image_id, D) -> (reports, context_reports)   # list[ReportEv]

Kurallar:
  * Pencere: rapor, çekimden önceki 0-120 dk içinde olmalı.
  * koordinat: rapor noktası kare merkezine <= 250 m. Veride koordinatlı 72 raporun her biri
    tam olarak bir görüntüye bağlanıyor (bkz. RAPOR_DOGRULAMA.md B4).
  * bolge: koordinatsız, metinde görüntünün bölgesinin adı geçiyor.
  * genel (context): ne koordinat ne bölge adı var. Aynı metin birden çok kez geliyorsa
    (ör. "Hava acik" x10) yalnızca en yenisi tutulur; bağlam olarak tekrar bilgi taşımaz.
Başka bölgeden söz eden raporlar bu görüntüye alınmaz.
checks alanı burada doldurulmaz: koordinatlı raporlar için checks.checks_for çağrılır.
"""
import math
from typing import TYPE_CHECKING

from dss.reports.claims import COORD_RE, hm, norm
from dss.schemas import ReportEv

if TYPE_CHECKING:
    from dss.evidence.builder import Data

REPORT_FRAME_RADIUS_M = 250
REPORT_WINDOW_MIN = 120


def frame_center(D: "Data", image_id: str) -> tuple[float, float]:
    c = D.meta[image_id]["corner_coordinates"]
    return (c["top_left"][0] + c["bottom_left"][0]) / 2, (c["top_left"][1] + c["top_right"][1]) / 2


def reports_for(image_id: str, D: "Data") -> tuple[list[ReportEv], list[ReportEv]]:
    cap = hm(D.meta[image_id]["capture_time"])
    clat, clon = frame_center(D, image_id)
    cx, cy = D.xy(clat, clon)
    zone = D.zone_of(clat, clon)
    zone_names = [norm(z["name"]) for z in D.zones]

    reports: list[ReportEv] = []
    context: dict[str, ReportEv] = {}
    for idx, r in enumerate(D.reports, 1):
        before = cap - hm(r["time"])
        if not 0 <= before <= REPORT_WINDOW_MIN:
            continue
        base = dict(report_id=f"R{idx:03d}", time=r["time"], source=r["source"], text=r["text"],
                    minutes_before_capture=before)
        t = norm(r["text"])
        if m := COORD_RE.search(r["text"]):
            lat, lon = float(m[1]), float(m[3])
            x, y = D.xy(lat, lon)
            dist = int(math.hypot(x - cx, y - cy))
            if dist <= REPORT_FRAME_RADIUS_M:
                reports.append(ReportEv(**base, scope="koordinat", lat=lat, lon=lon, dist_to_frame_center_m=dist))
        elif norm(zone) in t:
            reports.append(ReportEv(**base, scope="bolge"))
        elif not any(z in t for z in zone_names):
            prev = context.get(t)
            if prev is None or before < prev.minutes_before_capture:
                context[t] = ReportEv(**base, scope="genel")

    return reports, sorted(context.values(), key=lambda r: r.report_id)

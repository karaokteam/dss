"""
Kanıt paketi oluşturucu: tespitler + meta + zones + tracks + raporlar → EvidencePack.
Geo/track fonksiyonları ekip arkadaşının modülünden gelecek; burada bağımsız çalışsın
diye basit sürümleri var. Arayüz aynı kalırsa import satırını değiştirmek yeterli.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from dss.reports.association import reports_for
from dss.reports.checks import checks_for
from dss.schemas import (LEVEL_ORDER, DetectionEv, EvidencePack, HardFlag, ImageInfo,
                     MotionEv, StopEv, UnmatchedTrack, ZoneSummary)

# ── Parametreler (kalibre edilecek) ──
MATCH_MAX_M = 15
STOP_SPEED = 0.5                 # m/s
R = 6_371_000


class Data:
    def __init__(self, root: str | Path):
        root = Path(root)
        self.meta = json.loads((root / "image_meta.json").read_text(encoding="utf-8"))
        z = json.loads((root / "zones.json").read_text(encoding="utf-8"))
        self.base, self.zones = z["base"], z["zones"]
        self.reports = json.loads((root / "field_reports.json").read_text(encoding="utf-8"))
        t = pd.read_csv(root / "tracks.csv", dtype={"time": str})
        t["t"] = t["time"].map(hm)
        t["x"], t["y"] = zip(*[self.xy(a, b) for a, b in zip(t.lat, t.lon)])
        t["d"] = np.hypot(t.x, t.y)
        self.tracks = t.sort_values(["track_id", "t"])

    def xy(self, lat, lon):
        c = math.cos(math.radians(self.base["lat"]))
        return (math.radians(lon - self.base["lon"]) * R * c,
                math.radians(lat - self.base["lat"]) * R)

    def zone_of(self, lat, lon):
        x, y = self.xy(lat, lon)
        return min(self.zones, key=lambda z: math.dist((x, y), self.xy(*z["center"])))["name"]


def hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


CARDINAL = ["K", "KD", "D", "GD", "G", "GB", "B", "KB"]


def motion(D: Data, tid: str, det_id=None) -> MotionEv:
    tr = D.tracks[D.tracks.track_id == tid]
    x, y, d, times = tr.x.values, tr.y.values, tr.d.values, tr.time.values
    seg = np.hypot(np.diff(x), np.diff(y)) / 300
    moving = seg[seg >= STOP_SPEED]

    stops, i = [], 0
    while i < len(seg):
        if seg[i] < STOP_SPEED:
            j = i
            while j + 1 < len(seg) and seg[j + 1] < STOP_SPEED:
                j += 1
            if (j - i + 1) * 5 >= 15:
                stops.append(StopEv(start=times[i], end=times[j + 1],
                                    minutes=(j - i + 1) * 5, dist_to_base_m=int(d[i])))
            i = j + 1
        else:
            i += 1

    k = 6  # son 30 dk
    vx, vy = x[-1] - x[-1 - k], y[-1] - y[-1 - k]
    heading = (math.degrees(math.atan2(vx, vy)) + 360) % 360
    nv, npos = math.hypot(vx, vy), math.hypot(x[-1], y[-1])
    cos = -(vx * x[-1] + vy * y[-1]) / (nv * npos) if nv > 1 and npos > 1 else 0.0
    approach = (d[-1 - k] - d[-1]) / (k * 300)
    eta = d[-1] / approach / 60 if approach > 0.3 else None

    if nv < 50:
        pattern = "sabit"
    elif approach > 0.3 and stops:
        pattern = "duraklayip_yaklasiyor"
    elif approach > 0.3:
        pattern = "yaklasiyor"
    elif approach < -0.3:
        pattern = "uzaklasiyor"
    elif seg.sum() * 300 > 3 * abs(d[-1] - d[0]) + 500:
        pattern = "dolaniyor"
    else:
        pattern = "teget_geciyor"

    return MotionEv(
        track_id=tid, det_id=det_id, window=f"{times[0]}-{times[-1]}",
        dist_start_m=int(d[0]), dist_min_m=int(d.min()), dist_now_m=int(d[-1]),
        approach_rate_30m_mps=round(float(approach), 2),
        avg_speed_mps=round(float(moving.mean()), 1) if len(moving) else 0.0,
        speed_last_30m_mps=round(nv / (k * 300), 1),
        heading_deg=int(heading), heading_cardinal=CARDINAL[int((heading + 22.5) // 45) % 8],
        toward_base_cos=round(float(cos), 2), path_len_m=int(seg.sum() * 300),
        eta_min=round(eta, 1) if eta else None, stops=stops, pattern=pattern)


def build_pack(D: Data, image_id: str, raw_dets: list[dict]) -> EvidencePack:
    """raw_dets: [{"label","conf","lat","lon"}] — tespit modülünün çıktısı."""
    m = D.meta[image_id]
    c = m["corner_coordinates"]
    clat = (c["top_left"][0] + c["bottom_left"][0]) / 2
    clon = (c["top_left"][1] + c["top_right"][1]) / 2
    cx, cy = D.xy(clat, clon)
    fw = D.xy(clat, c["top_right"][1])[0] - D.xy(clat, c["top_left"][1])[0]
    fh = D.xy(c["top_left"][0], clon)[1] - D.xy(c["bottom_left"][0], clon)[1]
    cap = m["capture_time"]
    zone = D.zone_of(clat, clon)

    img = ImageInfo(image_id=image_id, capture_time=cap, width_px=m["width_px"],
                    height_px=m["height_px"], zone=zone, center_lat=clat, center_lon=clon,
                    dist_to_base_m=int(math.hypot(cx, cy)), footprint_m=(int(fw), int(fh)))

    # ── Tespitler + Hungarian yerine basit açgözlü eşleştirme (ekip modülüyle değişecek)
    at_cap = D.tracks[D.tracks.time == cap]
    dets, used = [], set()
    for i, rd in enumerate(raw_dets, 1):
        x, y = D.xy(rd["lat"], rd["lon"])
        dd = np.hypot(at_cap.x - x, at_cap.y - y)
        dd = dd[~at_cap.track_id.isin(used)]
        tid, md = None, None
        if len(dd) and dd.min() <= MATCH_MAX_M:
            tid = at_cap.loc[dd.idxmin(), "track_id"]; md = round(float(dd.min()), 1); used.add(tid)
        dets.append(DetectionEv(det_id=f"D{i}", label=rd["label"], conf=rd["conf"],
                                lat=rd["lat"], lon=rd["lon"], dist_to_base_m=int(math.hypot(x, y)),
                                track_id=tid, match_dist_m=md))

    motions = [motion(D, d.track_id, d.det_id) for d in dets if d.track_id]
    unmatched = []
    for _, r in at_cap[~at_cap.track_id.isin(used)].iterrows():
        dx = max(abs(r.x - cx) - fw / 2, 0); dy = max(abs(r.y - cy) - fh / 2, 0)
        dist = int(math.hypot(dx, dy))
        if dist < 300:  # kareye yakın olanlar ilgili; uzaktakiler başka görüntünün
            unmatched.append(UnmatchedTrack(track_id=r.track_id, dist_to_frame_m=dist,
                             reason="karede_ama_tespit_yok" if dist == 0 else "kare_disinda"))
            motions.append(motion(D, r.track_id))

    counts = {}
    for d in dets:
        counts[d.label] = counts.get(d.label, 0) + 1
    zs = ZoneSummary(zone=zone, detected_counts=counts,
                     heavy_vehicle_present=any(d.label in ("truck", "bus") for d in dets))

    # ── Raporlar (Kişi 4: dss/reports/)
    reports, context = reports_for(image_id, D)
    for r in reports:
        if r.scope == "koordinat":
            r.checks = checks_for(r, dets, cap, D)

    # ── Sert bayraklar
    flags = []
    def add(code, desc, ev, lvl):
        flags.append(HardFlag(flag_id=f"F{len(flags)+1}", code=code, description=desc,
                              evidence=ev, min_level=lvl))
    label_of = {d.track_id: d.label for d in dets if d.track_id}
    for mo in motions:
        lbl = label_of.get(mo.track_id)
        ev = [mo.track_id] + ([mo.det_id] if mo.det_id else [])
        if mo.eta_min is not None and mo.eta_min < 10:
            add("YAKIN_VARIS", f"{mo.track_id} mevcut hızla ~{mo.eta_min} dk'da üsse ulaşır", ev, "KRITIK")
        elif mo.dist_now_m < 1500 and mo.approach_rate_30m_mps > 1:
            add("YAKIN_YAKLASMA", f"{mo.track_id} üsse {mo.dist_now_m} m, yaklaşıyor", ev, "YUKSEK")
        if lbl in ("truck", "bus") and mo.dist_now_m < 3000:
            add("AGIR_ARAC_YAKIN", f"{lbl} üsse {mo.dist_now_m} m", ev, "ORTA")
        if any(s.minutes >= 30 and s.dist_to_base_m < 2000 for s in mo.stops):
            add("UZUN_BEKLEME_YAKIN", f"{mo.track_id} üsse 2 km içinde ≥30 dk bekledi", ev, "ORTA")
    for d in dets:
        if d.label in ("truck", "bus") and not d.track_id and d.dist_to_base_m < 3000:
            add("IZSIZ_AGIR_ARAC", f"{d.det_id} ({d.label}) hareket kaydı yok, üsse {d.dist_to_base_m} m",
                [d.det_id], "ORTA")

    floor = max((f.min_level for f in flags), key=LEVEL_ORDER.index, default="DUSUK")
    return EvidencePack(image=img, detections=dets, motions=motions, unmatched_tracks=unmatched,
                        zone_summary=zs, reports=reports, context_reports=context,
                        hard_flags=flags, rule_floor=floor)

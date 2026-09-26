"""Kişi 4 · rapor ayrıştırma, ilişkilendirme, kontroller ve izleme.

Vakalar RAPOR_DOGRULAMA.md ve eval/gold_reports.json'daki bulgulardan. Tespit listesi boş verilir:
hedef araç çekim anındaki track'ten bulunduğu için testler Kişi 1'in çıktısına bağlı değildir.
"""
import json
from functools import lru_cache
from pathlib import Path

import pytest

from dss.reports.association import reports_for
from dss.reports.checks import checks_for
from dss.reports.claims import parse_claim
from dss.reports.trace import trace_for
from dss.schemas import ReportEv

ROOT = Path(__file__).parents[1]


@lru_cache
def data():
    from dss.evidence.builder import Data
    return Data(ROOT / "data")


def report(image_id: str, rid: str) -> ReportEv:
    reports, _ = reports_for(image_id, data())
    return next(r for r in reports if r.report_id == rid)


# ── claims ──────────────────────────────────────────────────────────────────

def test_every_report_gets_a_category():
    D = data()
    missing = [i for i, r in enumerate(D.reports, 1) if parse_claim(r["text"], D.zones).category is None]
    assert missing == []


@pytest.mark.parametrize("text, expected", [
    ("39.92087N 32.89536E konumundaki kamyon bir saatten uzun suredir yerinden ayrilmadi.",
     dict(category="hareketsizlik", vehicle_class="truck", count=1, duration_min=60, coord_decimals=5)),
    ("39.9307N 32.8380E yakininda 5 kamyonun durdugu bildirildi.",
     dict(category="hareketsizlik", count=5, coord_decimals=4)),
    ("39.95395N 32.84430E konumundan usse dogru ilerleyen otomobil planli ikmal aracidir, kimlik teyidi yapilmistir.",
     dict(category="dost_kimlik", motion="usse_yaklasiyor", identity=True)),
    ("39.91309N 32.80343E konumunda uzeri ortulu bir agir arac bekliyor.",
     dict(category="hareketsizlik", vehicle_class="heavy", visual=("ortulu",))),
    ("Planli tatbikat nedeniyle gun icinde bolgede dost unsurlar bulunacak.", dict(category="gurultu")),
    ("Dun gece Dogu Yolu cevresinde arac hareketliligi oldugu yonunde dogrulanmamis bir ihbar var.",
     dict(category="gurultu", past_event=True, zone="Dogu Yolu")),
    # veride olmayan bir cümle: Türkçe karakter, yeni fiil, saat cinsinden süre
    ("Güney Kapısı Yaklaşımı civarında 3 saattir bekleyen bir kamyon var.",
     dict(category="hareketsizlik", vehicle_class="truck", duration_min=180, zone="Guney Kapisi Yaklasimi")),
])
def test_parse_claim(text, expected):
    c = parse_claim(text, data().zones)
    assert {k: getattr(c, k) for k in expected} == expected


# ── association ─────────────────────────────────────────────────────────────

def test_every_coordinate_report_links_to_exactly_one_image():
    D = data()
    seen: dict[str, list[str]] = {}
    for image_id in D.meta:
        for r in reports_for(image_id, D)[0]:
            if r.scope == "koordinat":
                seen.setdefault(r.report_id, []).append(image_id)
    assert len(seen) == 72 and all(len(v) == 1 for v in seen.values())


def test_context_reports_are_deduplicated():
    for image_id in data().meta:
        texts = [r.text for r in reports_for(image_id, data())[1]]
        assert len(texts) == len(set(texts))


# ── checks ──────────────────────────────────────────────────────────────────

def test_checks_for_stationary_track_near_r001():
    ch = checks_for(report("img_003839", "R001"), [], "13:25", data())
    assert ch.tracks_near_at_report_time[0].track_id == "T0182"
    assert "T0182" in ch.stationary_tracks_near


# ── trace: raporun anlattığı aracı izleme ───────────────────────────────────

def trace(image_id, rid):
    return trace_for(report(image_id, rid), [], image_id, data())


def test_friendly_claim_vehicle_actually_moving_away_r007():
    t = trace("img_001230", "R007")
    assert t.target_track == "T0131" and t.target_approach_30m_before_report_m < -1500


def test_friendly_claim_vehicle_fast_approaching_r113():
    t = trace("img_000733", "R113")
    assert t.target_track == "T0124" and t.target_approach_30m_before_report_m > 3000


def test_undetected_truck_found_through_track_r033():
    """0,25 eşiğinde tespit edilmeyen kamyon, çekim anındaki track'ten bulunur."""
    t = trace("img_005788", "R033")
    assert t.target_track == "T0223" and t.duration_max_move_m < 25


def test_full_duration_coverage_r015():
    t = trace("img_001643", "R015")
    assert (t.claimed_duration_min, t.duration_covered_min) == (60, 60) and t.duration_max_move_m <= 25


def test_partial_duration_coverage_r053():
    t = trace("img_000267", "R053")
    assert t.duration_covered_min == 35 and t.claimed_duration_min == 60


def test_phantom_report_has_no_vehicle_r039():
    t = trace("img_003189", "R039")
    assert t.target_track is None and t.target_det is None and t.followed_tracks == []


def test_followed_track_stays_in_frame_r001():
    f = trace("img_003839", "R001").followed_tracks[0]
    assert f.track_id == "T0182" and f.in_frame_at_capture and f.moved_until_capture_m < 25


# ── builder entegrasyonu ve altın set ───────────────────────────────────────

def test_builder_uses_report_modules():
    from dss.evidence.builder import build_pack
    pack = build_pack(data(), "img_003839", [])
    coord = [r for r in pack.reports if r.scope == "koordinat"]
    assert coord and all(r.checks is not None for r in coord)


def test_gold_labels_point_to_reports_in_packs():
    gold = json.loads((ROOT / "eval" / "gold_reports.json").read_text(encoding="utf-8"))["labels"]
    for g in gold:
        ids = {r.report_id for r in reports_for(g["image_id"], data())[0]}
        assert g["report_id"] in ids, f'{g["image_id"]}/{g["report_id"]} pakette yok'


# ── zone_checks: bölge adıyla yazılmış raporlar ─────────────────────────────

@lru_cache
def zone_inputs():
    from dss.reports.zone_checks import load_detections_file, track_classes
    dets = load_detections_file(ROOT / "data" / "image_box_and_reports" / "detections_all_ge0.10.json")
    return track_classes(data(), dets), dets


def zone(image_id, rid):
    from dss.reports.zone_checks import zone_checks_for
    return zone_checks_for(report(image_id, rid), data(), *zone_inputs())


def test_track_classes_cover_most_tracks_and_rescue_low_conf_truck():
    classes, _ = zone_inputs()
    assert len(classes) >= 190
    assert classes["T0122"].label == "truck" and classes["T0122"].conf < 0.25   # track destekli 0,10


def test_heavy_vehicle_contradicts_no_heavy_claim_r017():
    z = zone("img_004530", "R017")
    assert z.zone == "Guney Kapisi Yaklasimi" and "T0174" in {v.track_id for v in z.heavy}


def test_no_heavy_seen_r100():
    z = zone("img_005561", "R100")
    assert z.heavy == [] and z.vehicles_seen > 0


def test_near_arrival_anomaly_r042():
    z = zone("img_001733", "R042")
    t0034 = next(v for v in z.anomalies if v.track_id == "T0034")
    assert "YAKIN_VARIS" in t0034.flags and t0034.dist_to_base_m < 1000


def test_radio_gap_linked_r099():
    assert "R065" in zone("img_003464", "R099").radio_gap_reports


def test_morning_patrol_is_context_not_claim():
    reports, context = reports_for("img_005672", data())
    assert "R008" not in {r.report_id for r in reports}
    assert "R008" in {r.report_id for r in context}

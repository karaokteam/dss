from collections import Counter

import pytest

from backend.engine.data.repository import get_repository
from backend.engine.geo.zones import nearest_zone
from backend.engine.models import ClaimType
from backend.engine.reports.claim_parser import (
    ParseError, claim_from_llm_json, compare, load_claims, parse_all, parse_rules, save_claims,
)
from backend.engine.reports.extract import extract, parse_coordinate, vehicle_type_in
from backend.engine.reports.linker import link_all
from backend.tests.conftest import SAMPLE_IMAGE, SAMPLE_TRUCK_TRACK


@pytest.fixture(scope="module")
def repo():
    return get_repository()


@pytest.fixture(scope="module")
def claims(repo):
    return parse_all(repo.reports(), repo.zones, mode="rules")


@pytest.fixture(scope="module")
def links(repo, claims):
    return link_all(repo, claims)


def _claim(repo, text):
    r = next(r for r in repo.reports() if r.text.startswith(text))
    return parse_rules(r, extract(r.text, repo.zones))


# ---------------------------------------------------------------- extract

def test_coordinate_parsing():
    lat, lon, prec = parse_coordinate("39.9374N 32.8483E civarinda")
    assert (lat, lon) == (39.9374, 32.8483) and prec == pytest.approx(5.6, abs=0.1)
    assert parse_coordinate("39.92087N 32.89536E")[2] == pytest.approx(0.6, abs=0.1)
    assert parse_coordinate("39.9374 N, 32.8483 E")[:2] == (39.9374, 32.8483)
    assert parse_coordinate("12.5S 45.1W")[:2] == (-12.5, -45.1)
    assert parse_coordinate("Hava acik") is None


def test_vehicle_words():
    assert vehicle_type_in("1 agir arac kamyon otobus gozlendi") == "heavy"
    assert vehicle_type_in("agir bir aracin beklemede") == "heavy"
    assert vehicle_type_in("otobus duruyor") == "bus"
    assert vehicle_type_in("usse dogru ilerleyen otomobil planli ikmal aracidir") == "car"
    assert vehicle_type_in("mavi arac dost") == "vehicle"


def test_categories(repo):
    cats = Counter(extract(r.text, repo.zones).category for r in repo.reports())
    assert cats == {"coordinate": 72, "zone": 43, "general": 22}


# ---------------------------------------------------------------- kural parser

def test_rules_cover_every_report(claims):
    assert not [c for c in claims.values() if c.claim_types == (ClaimType.UNKNOWN,)]


def test_rule_examples(repo):
    c = _claim(repo, "39.92087N 32.89536E konumundaki kamyon")
    assert c.claim_types == (ClaimType.STATIONARY,) and c.vehicle_type == "truck" and c.stationary_min == 60

    c = _claim(repo, "39.9209N 32.8953E yakininda 2 kamyonun")
    assert c.claim_types == (ClaimType.COUNT, ClaimType.STATIONARY) and c.count == 2 and c.hedged

    c = _claim(repo, "39.92083N 32.89617E konumundan usse dogru")
    assert c.claim_types[0] == ClaimType.IDENTITY and c.friendly and c.motion == "approaching_base"

    c = _claim(repo, "39.92516N 32.88412E civarindan usse gelen otomobil bize bagli")
    assert c.friendly and not c.hedged   # "gelişi önceden bildirilmiştir" çekince değil

    c = _claim(repo, "39.9017N 32.8702E civarinda 3 araclik")
    assert c.count == 3 and c.vehicle_type == "truck" and c.motion == "moving"

    c = _claim(repo, "39.9094N 32.8281E cevresinde trafik olagandan yogun")
    assert c.claim_types == (ClaimType.DENSITY,) and c.normal_count == 4 and c.count is None

    c = _claim(repo, "Bir kaynak, 39.92043N")
    assert c.vehicle_type == "heavy" and c.hedged

    c = _claim(repo, "Kuzeydogu Kavsagi bolgesinde agir arac hareketi yok")
    assert c.zone_status == "no_heavy" and c.count == 0 and c.zone == "Kuzeydogu Kavsagi"

    c = _claim(repo, "Planli tatbikat")
    assert c.claim_types == (ClaimType.NOISE,) and c.blanket_friendly and not c.friendly


# ---------------------------------------------------------------- LLM yanıt doğrulama (ağsız)

def test_llm_json_validation(repo):
    r = repo.report("R001")
    ex = extract(r.text, repo.zones)
    ok = claim_from_llm_json({"claim_types": ["count"], "vehicle_type": "truck", "count": 1,
                              "cargo": "unknown"}, r, ex)
    assert ok.parser == "llm" and ok.lat == ex.lat and ok.count == 1
    for bad in ({"claim_types": []}, {"claim_types": ["guess"]},
                {"claim_types": ["count"], "vehicle_type": "tank"},
                {"claim_types": ["count"], "count": -1}, {"claim_types": ["count"], "count": 2.5}):
        with pytest.raises(ParseError):
            claim_from_llm_json(bad, r, ex)


def test_compare_notes(repo):
    r = repo.report("R001")
    ex = extract(r.text, repo.zones)
    rules = parse_rules(r, ex)
    llm = claim_from_llm_json({"claim_types": ["count"], "vehicle_type": "truck", "count": 1,
                               "cargo": "unknown"}, r, ex)
    assert compare(llm, rules) == ()
    llm2 = claim_from_llm_json({"claim_types": ["count"], "vehicle_type": "car", "count": 1}, r, ex)
    assert compare(llm2, rules) == ("vehicle_type: llm=car rules=truck",)


def test_claims_roundtrip(tmp_path, claims):
    path = tmp_path / "claims.json"
    save_claims(claims, meta={"mode": "rules"}, path=path)
    assert load_claims(path) == claims


# ---------------------------------------------------------------- linker

def test_every_coordinate_report_links_to_one_image(claims, links):
    coord = [links[k] for k, c in claims.items() if c.category == "coordinate"]
    assert len(coord) == 72
    assert all(len(l.images) == 1 for l in coord)
    assert all(0 <= l.images[0].minutes_before_capture <= 120 for l in coord)


def test_track_proximity_split(claims, links):
    coord = [links[k] for k, c in claims.items() if c.category == "coordinate"]
    assert sum(any(t.dist_m <= 60 for t in l.tracks) for l in coord) == 47
    assert sum(not l.tracks for l in coord) == 20


def test_sample_links(links):
    l = links["R053"]   # 08:50 durağan kamyon
    assert l.images[0].image_id == SAMPLE_IMAGE and l.zone == "Dogu Yolu"
    assert l.tracks[0].track_id == SAMPLE_TRUCK_TRACK
    assert l.detections[0].detection_id == "img_000267_003"
    assert links["R101"].nearest_track_m > 1000   # "7 kamyon": rapor saatinde yakında track yok
    assert links["R101"].tracks == ()


def test_zone_links_stay_in_zone(repo, claims, links):
    for rid, c in claims.items():
        if c.category != "zone":
            continue
        for il in links[rid].images:
            assert nearest_zone(*repo.image(il.image_id).center, repo.zones)[0].name == c.zone
        assert links[rid].tracks == ()


def test_general_reports_have_no_links(claims, links):
    for rid, c in claims.items():
        if c.category == "general":
            assert links[rid].images == () and links[rid].zone is None

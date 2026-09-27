import re
from collections import Counter

import pytest

from backend.engine.data.repository import get_repository
from backend.engine.geo.geometry import (
    angle_diff_deg, bbox_center, bearing_deg, dist_to_base_m, distance_m,
    distance_to_footprint_m, in_footprint, latlon_to_pixel, pixel_to_latlon,
)
from backend.engine.geo.zones import (
    find_zones_in_text, nearest_zone, normalize_text, zone_by_name,
)
from backend.engine.models import Corners, ImageMeta
from backend.tests.conftest import SAMPLE_IMAGE, SAMPLE_TRUCK_TRACK

COORD_RE = re.compile(r"\d+\.\d+N\s+\d+\.\d+E")


@pytest.fixture(scope="module")
def repo():
    return get_repository()


@pytest.fixture
def pdf_image():
    """gorev_tanimi.pdf 'Uçtan uca örnek'teki temsili görüntü."""
    return ImageMeta(
        id="img_000123", width_px=1360, height_px=765, capture_min=805,
        corners=Corners(top_left=(39.94510, 32.86200), top_right=(39.94510, 32.86519),
                        bottom_left=(39.94373, 32.86200), bottom_right=(39.94373, 32.86519)),
        file=None,
    )


# ---------------------------------------------------------------- piksel ↔ koordinat

def test_pdf_example(pdf_image):
    cx, cy = bbox_center((610, 380, 60, 28))
    assert (cx, cy) == (640, 394)
    lat, lon = pixel_to_latlon(pdf_image, cx, cy)
    assert lon == pytest.approx(32.86350, abs=1e-5)
    assert lat == pytest.approx(39.94439, abs=1e-5)


def test_corners_map_exactly(pdf_image):
    assert pixel_to_latlon(pdf_image, 0, 0) == pytest.approx(pdf_image.corners.top_left)
    assert pixel_to_latlon(pdf_image, 1360, 0) == pytest.approx(pdf_image.corners.top_right)
    assert pixel_to_latlon(pdf_image, 0, 765) == pytest.approx(pdf_image.corners.bottom_left)


def test_roundtrip(pdf_image):
    lat, lon = pixel_to_latlon(pdf_image, 123.4, 567.8)
    assert latlon_to_pixel(pdf_image, lat, lon) == pytest.approx((123.4, 567.8), abs=1e-6)


def test_all_detections_match_given_coords(repo):
    """Bizim oranlamamız, detections.json'daki lat/lon ile 1 m'den az farklı olmalı."""
    worst = 0.0
    for det in repo.dataset.detections:
        img = repo.image(det.image_id)
        assert bbox_center(det.bbox_xywh) == pytest.approx(det.center_px)
        lat, lon = pixel_to_latlon(img, *det.center_px)
        worst = max(worst, distance_m(lat, lon, det.lat, det.lon))
    assert worst < 1.0


def test_detections_inside_their_image(repo):
    for det in repo.dataset.detections:
        assert in_footprint(repo.image(det.image_id), det.lat, det.lon)


# ---------------------------------------------------------------- mesafe / yön

def test_distance_known_values():
    # 0.001° enlem ≈ 111.2 m
    assert distance_m(39.92, 32.85, 39.921, 32.85) == pytest.approx(111.2, abs=0.5)
    assert distance_m(39.92, 32.85, 39.92, 32.85) == 0


def test_bearing_cardinal(repo):
    b = repo.base
    north = zone_by_name("Kuzey Yolu", repo.zones)
    east = zone_by_name("Dogu Yolu", repo.zones)
    assert bearing_deg(b.lat, b.lon, north.lat, north.lon) == pytest.approx(0, abs=0.5)
    assert bearing_deg(b.lat, b.lon, east.lat, east.lon) == pytest.approx(90, abs=0.5)
    assert angle_diff_deg(350, 10) == 20


def test_sample_distances(repo):
    img = repo.image(SAMPLE_IMAGE)
    assert dist_to_base_m(repo.base, *img.center) == pytest.approx(3631, abs=2)
    last = repo.track(SAMPLE_TRUCK_TRACK).last
    assert in_footprint(img, last.lat, last.lon)
    assert distance_to_footprint_m(img, last.lat, last.lon) == 0
    assert distance_to_footprint_m(img, last.lat + 0.001, last.lon) > 0


def test_images_1_6_to_5_5_km_from_base(repo):
    dists = [dist_to_base_m(repo.base, *img.center) for img in repo.images()]
    assert 1500 < min(dists) and max(dists) < 5500


# ---------------------------------------------------------------- bölgeler

def test_normalize_turkish():
    assert normalize_text("Güneybatı Yolu'nda") == "guneybati yolu nda"
    assert normalize_text("KUZEYDOĞU  Kavşağı") == "kuzeydogu kavsagi"


def test_zone_name_variants(repo):
    gb = zone_by_name("Guneybati Yolu", repo.zones)
    assert find_zones_in_text("Güneybatı Yolu'nda hareket var", repo.zones) == [gb]
    assert find_zones_in_text("guneybati yolunda hareket var", repo.zones) == [gb]
    # "Kuzey Yolu", "Kuzeybati Yolu" metninde eşleşmemeli
    names = [z.name for z in find_zones_in_text("Kuzeybati Yolu bolgesinde", repo.zones)]
    assert names == ["Kuzeybati Yolu"]


def test_zone_reports_detected(repo):
    """Veride 43 rapor bölge adı içeriyor; koordinatlı raporlarda bölge adı geçmiyor."""
    with_zone = [r for r in repo.reports() if find_zones_in_text(r.text, repo.zones)]
    assert len(with_zone) == 43
    assert not any(COORD_RE.search(r.text) for r in with_zone)
    assert all(len(find_zones_in_text(r.text, repo.zones)) == 1 for r in with_zone)


def test_nearest_zone(repo):
    img = repo.image(SAMPLE_IMAGE)
    zone, _ = nearest_zone(*img.center, repo.zones)
    assert zone.name == "Dogu Yolu"
    per_zone = Counter(nearest_zone(*i.center, repo.zones)[0].name for i in repo.images())
    assert sum(per_zone.values()) == 40

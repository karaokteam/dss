"""Step 0 — hazır altyapı."""

import pytest

from agent import config, loaders
from agent.fakes import fake_events, make_track
from agent.geo.spatial import bearing_deg, distance_m, nearest_zone
from agent.tracks.timeline import positions_at, series

S = config.SAMPLES_DIR


def test_distance_one_degree_latitude():
    assert distance_m((39.0, 32.0), (40.0, 32.0)) == pytest.approx(111_195, rel=1e-3)


def test_bearing_cardinals():
    assert bearing_deg((39.0, 32.0), (40.0, 32.0)) == pytest.approx(0, abs=1e-6)
    assert bearing_deg((39.0, 32.0), (39.0, 33.0)) == pytest.approx(90, abs=1)


def test_nearest_zone(zones_sample):
    assert nearest_zone((39.95, 32.853), zones_sample) == "Kuzey Yolu"


def test_series_sorted_and_cut():
    pts = list(reversed(make_track()))
    assert [p.time for p in series(pts, "T0122", until="14:05")] == ["14:00", "14:05"]


def test_positions_at_interpolates():
    p = positions_at(make_track(), "14:02")["T0122"]
    assert p.time == "14:02" and 39.9257 < p.lat < 39.9260


def test_positions_at_tolerance():
    assert "T0122" in positions_at(make_track(), "14:14", tolerance_min=5)
    assert "T0122" not in positions_at(make_track(), "14:30", tolerance_min=5)


def test_loaders_on_samples():
    assert loaders.load_image_meta(S / "image_meta_sample.json")["img_000860"].capture_time == "14:10"
    assert loaders.load_zones(S / "zones_sample.json").base.name == "Merkez Us"
    assert loaders.load_tracks(S / "tracks_sample.csv")[0].track_id == "T0001"
    assert loaders.load_reports(S / "field_reports_sample.json")[1].report_id == "R001"


def test_fake_events_end_with_assessment():
    last = list(fake_events())[-1]
    assert last.name == "brief" and last.payload["assessment"].findings

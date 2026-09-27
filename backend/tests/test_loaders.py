from collections import Counter

import pytest

from backend.engine.data.repository import get_repository
from backend.engine.models import Source, fmt_hhmm, parse_hhmm
from backend.tests.conftest import SAMPLE_IMAGE, SAMPLE_TRUCK_DET, SAMPLE_TRUCK_TRACK


@pytest.fixture(scope="module")
def repo():
    return get_repository()


def test_time_roundtrip():
    assert parse_hhmm("13:25") == 805
    assert fmt_hhmm(805) == "13:25"
    with pytest.raises(ValueError):
        parse_hhmm("25:00")


def test_counts(repo):
    assert len(repo.images()) == 40
    assert len(repo.dataset.detections) == 323
    assert len(repo.tracks()) == 226
    assert len(repo.reports()) == 137
    assert len(repo.zones) == 8
    assert repo.warnings == ()


def test_detection_labels(repo):
    labels = Counter(d.label for d in repo.dataset.detections)
    assert labels == {"car": 250, "truck": 40, "van": 29, "bus": 4}


def test_images_have_files(repo):
    for img in repo.images():
        assert img.file.exists(), img.file
        assert img.annotated_file is not None and img.annotated_file.exists()


def test_tracks_are_two_hours_on_5min_grid(repo):
    for tr in repo.tracks():
        assert len(tr.points) == 25
        steps = {b.t - a.t for a, b in zip(tr.points, tr.points[1:])}
        assert steps == {5}


def test_every_track_ends_at_an_image_capture(repo):
    capture_times = {img.capture_min for img in repo.images()}
    for tr in repo.tracks():
        assert tr.end_min in capture_times
        assert tr.image_id is not None
        assert repo.image(tr.image_id).capture_min == tr.end_min


def test_report_ids_and_sources(repo):
    ids = [r.id for r in repo.reports()]
    assert len(set(ids)) == 137
    assert repo.report("R001").index == 0
    sources = Counter(r.source for r in repo.reports())
    assert sources == {Source.OFFICIAL: 98, Source.THIRD_PARTY: 39}
    times = [r.t for r in repo.reports()]
    assert times == sorted(times)


def test_sample_objects(repo):
    det = repo.detection(SAMPLE_TRUCK_DET)
    assert det.label == "truck" and det.image_id == SAMPLE_IMAGE
    tr = repo.track(SAMPLE_TRUCK_TRACK)
    assert tr.image_id == SAMPLE_IMAGE
    assert repo.image(SAMPLE_IMAGE).capture_time == "10:15"
    assert SAMPLE_TRUCK_TRACK in {t.id for t in repo.tracks_for_image(SAMPLE_IMAGE)}
    assert len(repo.detections_for(SAMPLE_IMAGE)) == 6


def test_track_at_exact_and_interpolated(repo):
    tr = repo.track(SAMPLE_TRUCK_TRACK)
    a, b = tr.points[0], tr.points[1]
    assert repo.track_at(tr.id, a.t) == a
    mid = repo.track_at(tr.id, a.t + 2)
    assert min(a.lat, b.lat) <= mid.lat <= max(a.lat, b.lat)
    assert repo.track_at(tr.id, tr.start_min - 5) is None
    assert repo.track_at(tr.id, tr.end_min + 5) is None


def test_reports_between(repo):
    window = repo.reports_between(parse_hhmm("08:45"), parse_hhmm("08:50"))
    assert {r.time for r in window} == {"08:45", "08:50"}
    third_party = repo.reports_between(0, 24 * 60, source=Source.THIRD_PARTY)
    assert len(third_party) == 39


def test_unknown_ids_raise(repo):
    with pytest.raises(KeyError):
        repo.image("img_nope")
    with pytest.raises(KeyError):
        repo.track("T9999")

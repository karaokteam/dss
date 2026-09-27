from collections import Counter

import pytest

from backend.engine.data.repository import get_repository
from backend.engine.fusion.kinematics import compute_kinematics, track_state_at
from backend.engine.fusion.matcher import match_all, match_image
from backend.engine.models import Base, Track, TrackPoint, parse_hhmm
from backend.tests.conftest import SAMPLE_IMAGE, SAMPLE_TRUCK_DET, SAMPLE_TRUCK_TRACK


@pytest.fixture(scope="module")
def repo():
    return get_repository()


@pytest.fixture(scope="module")
def matches(repo):
    return match_all(repo)


# ---------------------------------------------------------------- eşleştirme

def test_one_to_one_counts(matches):
    assert sum(len(m.matches) for m in matches.values()) == 202
    assert sum(len(m.unmatched_detections) for m in matches.values()) == 121
    unmatched = [u for m in matches.values() for u in m.unmatched_tracks]
    assert len(unmatched) == 24
    assert sum(u.in_frame for u in unmatched) == 4


def test_matches_are_one_to_one(matches):
    for m in matches.values():
        tracks = [x.track_id for x in m.matches]
        dets = [x.detection_id for x in m.matches]
        assert len(tracks) == len(set(tracks))
        assert len(dets) == len(set(dets))


def test_every_track_accounted_for(repo, matches):
    seen = Counter()
    for m in matches.values():
        seen.update(x.track_id for x in m.matches)
        seen.update(u.track_id for u in m.unmatched_tracks)
    assert set(seen) == {t.id for t in repo.tracks()}
    assert max(seen.values()) == 1


def test_gate_is_not_sensitive(repo):
    """Veride 3 m ile 15 m arası kapılar neredeyse aynı sonucu verir."""
    at3 = sum(len(m.matches) for m in match_all(repo, gate_m=3).values())
    at15 = sum(len(m.matches) for m in match_all(repo, gate_m=15).values())
    assert 200 <= at3 <= at15 <= 205


def test_sample_match(repo):
    m = match_image(repo, SAMPLE_IMAGE)
    assert m.track_for(SAMPLE_TRUCK_DET) == SAMPLE_TRUCK_TRACK
    assert m.detection_for(SAMPLE_TRUCK_TRACK) == SAMPLE_TRUCK_DET


def test_close_neighbours_not_ambiguous(repo):
    """img_003201'de iki araç 2 m arayla duruyor; Hungarian doğru atar, alternatif üretmez."""
    m = match_image(repo, "img_003201")
    assert all(x.dist_m < 1 for x in m.matches)
    assert not any(x.alternatives for x in m.matches)


# ---------------------------------------------------------------- kinematik

def test_stationary_truck(repo):
    k = compute_kinematics(repo.track(SAMPLE_TRUCK_TRACK), repo.base)
    assert k.state == "stationary" and k.motion == "stationary"
    assert k.stationary_min == 120 and k.moves == 0
    assert k.eta_min is None and k.tortuosity is None
    assert abs(k.radial_change_window_m) < 30   # titreme radyal sinyal üretmez


def test_consistent_approacher(repo):
    """T0020: 2 saatte üsse ~6,2 km yaklaşıp 1,6 km'de durmuş."""
    k = compute_kinematics(repo.track("T0020"), repo.base)
    assert k.consistent_approach
    assert k.motion == "approaching"
    assert k.radial_change_window_m < -3000
    assert k.dist_to_base_m == pytest.approx(1603, abs=5)
    assert k.heading_to_base_diff_deg < 10
    assert k.stationary_min == 50 and k.eta_min is None   # durduğu için ETA verilmez


def test_consistent_approach_is_rare(repo):
    flags = [compute_kinematics(t, repo.base).consistent_approach for t in repo.tracks()]
    assert sum(flags) == 7


def test_state_at_report_time_uses_only_past(repo):
    """08:50 raporu: T0045 kaydı 08:15'te başlıyor → en az 35 dk durağan görülebilir."""
    k = track_state_at(repo.track(SAMPLE_TRUCK_TRACK), repo.base, parse_hhmm("08:50"))
    assert k.at == "08:50"
    assert k.stationary_min == 35 == k.observed_min
    assert track_state_at(repo.track(SAMPLE_TRUCK_TRACK), repo.base, parse_hhmm("08:00")) is None


def test_segments_cover_the_whole_track(repo):
    for t in repo.tracks():
        k = compute_kinematics(t, repo.base)
        assert sum(s.duration_min for s in k.segments) == 120
        assert sum(s.kind == "move" for s in k.segments) <= k.moves


def test_synthetic_approach_eta():
    """Üsse doğru sabit hızla giden araç: radyal hız ≈ −hız, ETA = uzaklık / hız."""
    base = Base("B", 40.0, 33.0)
    # her 5 dakikada 0.01° (~1112 m) güneye, üsse doğru
    pts = tuple(TrackPoint(t=600 + 5 * i, lat=40.2 - 0.01 * i, lon=33.0) for i in range(13))
    k = compute_kinematics(Track("X", pts), base)
    assert k.motion == "approaching" and k.state == "moving"
    assert k.radial_speed_mps == pytest.approx(-3.71, abs=0.02)
    assert k.speed_mps == pytest.approx(3.71, abs=0.02)
    assert k.eta_min == pytest.approx(k.dist_to_base_m / 3.706 / 60, rel=0.01)
    assert k.consistent_approach and k.tortuosity == pytest.approx(1.0, abs=0.01)

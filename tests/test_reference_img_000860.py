"""SON-1 · Uçtan uca referans: img_000860 → truck · T0122 · üsse ~1,6 km."""

import pytest

from tests.conftest import requires_raw_data


@requires_raw_data
def test_img_000860_end_to_end():
    pytest.skip("SON-1: pipeline hazır olunca bu satırı sil")
    from agent.pipeline import run

    a = run("img_000860")
    trucks = [f for f in a.findings if f.geo.detection.cls == "truck"]
    t = next(f for f in trucks if f.track_id == "T0122")
    assert 1400 < t.geo.distance_to_base_m < 1800

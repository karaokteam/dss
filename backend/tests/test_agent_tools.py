import json

import pytest

from backend.engine.agent.tools import call, get_tools, registry, tool
from backend.engine.analysis.consistency import get_context


@pytest.fixture(scope="module")
def ctx():
    return get_context()


# ---------------------------------------------------------------- registry

def test_only_ambiguity_tools_registered():
    """Tool'lar yalnızca agent'ın belirsizlikte karar verdiği soruşturmalar içindir."""
    assert set(registry()) == {"vehicles_in_area", "co_movement", "inspect_image"}


def test_schemas_are_valid_openai_tools():
    tools = {t["function"]["name"]: t for t in get_tools()}
    area = tools["vehicles_in_area"]["function"]
    assert area["parameters"]["required"] == ["lat", "lon", "radius_m", "time_from", "time_to"]
    assert area["parameters"]["properties"]["vehicle_type"]["enum"] == ["car", "van", "truck", "bus", "heavy"]
    assert area["parameters"]["properties"]["lat"]["type"] == "number"
    assert area["parameters"]["properties"]["radius_m"]["description"]
    co = tools["co_movement"]["function"]
    assert co["parameters"]["properties"]["track_ids"] == {
        "type": "array", "items": {"type": "string"}, "description": co["parameters"]["properties"]["track_ids"]["description"]}
    json.dumps(get_tools())


def test_call_never_raises():
    assert "Bilinmeyen tool" in call("nope", {})["error"]
    assert "eksik" in call("vehicles_in_area", {"lat": 1, "lon": 2})["error"]
    assert "bilinmeyen" in call("co_movement", {"track_ids": ["T0019", "T0117"], "x": 1})["error"]
    assert "number" in call("vehicles_in_area", {"lat": "x", "lon": 2, "radius_m": 5,
                                                 "time_from": "10:00", "time_to": "11:00"})["error"]
    assert "JSON" in call("co_movement", "{bozuk")["error"]
    assert "geçersiz" in call("vehicles_in_area", {"lat": 39.9, "lon": 32.8, "radius_m": 50, "time_from": "10:00",
                                                   "time_to": "11:00", "vehicle_type": "tank"})["error"]
    assert "error" in call("co_movement", {"track_ids": ["T9999", "T0019"]})


def test_decorator_builds_schema_from_signature():
    @tool
    def _demo(a: int, b: list[str], c: bool = False) -> dict:
        """Demo tool.

        Args:
            a: bir sayı.
            b: liste.
        """
        return {"a": a, "b": b, "c": c}
    try:
        spec = registry()["_demo"]
        assert spec.parameters["required"] == ["a", "b"]
        assert spec.parameters["properties"]["a"] == {"type": "integer", "description": "bir sayı."}
        assert call("_demo", '{"a": "3", "b": ["x"]}') == {"a": 3, "b": ["x"], "c": False}
        assert "integer" in call("_demo", {"a": 2.5, "b": []})["error"]
    finally:
        from backend.engine.agent import tools as t
        t._REGISTRY.pop("_demo", None)


# ---------------------------------------------------------------- vehicles_in_area

def test_area_limits():
    base = {"lat": 39.9, "lon": 32.8, "time_from": "10:00"}
    assert "radius_m" in call("vehicles_in_area", {**base, "radius_m": 5000, "time_to": "11:00"})["error"]
    assert "180" in call("vehicles_in_area", {**base, "radius_m": 100, "time_to": "14:00"})["error"]
    assert "önce" in call("vehicles_in_area", {**base, "radius_m": 100, "time_to": "09:00"})["error"]


def test_area_finds_late_arrival_for_r007(ctx):
    """R007 (14:15) 'üsse gelen otomobil': o noktaya otomobil ancak çekimden hemen önce geliyor."""
    c = ctx.claims["R007"]
    r = call("vehicles_in_area", {"lat": c.lat, "lon": c.lon, "radius_m": 60,
                                  "time_from": "14:15", "time_to": "15:15"})
    first = r["tracked"][0]
    assert first["track_id"] == "T0131" and first["label"] == "car"
    assert first["present"] == "15:15–15:15" and first["arrived_during_window"]


def test_area_type_filter_and_parked(ctx):
    c = ctx.claims["R101"]   # "7 kamyon durdu" (11:40)
    r = call("vehicles_in_area", {"lat": c.lat, "lon": c.lon, "radius_m": 100, "time_from": "11:40",
                                  "time_to": "12:15", "vehicle_type": "heavy"})
    assert all(t["label"] in ("truck", "bus", None) for t in r["tracked"])
    assert all(t["arrived_during_window"] for t in r["tracked"])   # kamyonlar rapordan SONRA geliyor
    assert r["parked_count"] >= 1 and all(p["confidence"] >= 0.3 for p in r["parked"])


# ---------------------------------------------------------------- co_movement

def test_waiting_together():
    r = call("co_movement", {"track_ids": ["T0019", "T0117"]})
    assert r["pairs"][0]["relation"] == "waiting_together"


def test_converged_pair_reports_chance_rate():
    """img_003464: T0028 ve T0001 4 kez aynı anda aynı yöne hareketle buluştu. Tesadüf oranı ~%5 döner;
    çoklu karşılaştırmada bu oran tek başına sinyal değildir (uyarı çıktıda)."""
    r = call("co_movement", {"track_ids": ["T0028", "T0001"]})
    pair = r["pairs"][0]
    assert pair["relation"] == "converged_in_step"
    assert pair["same_direction_moves"] >= 4 and pair["chance_rate"] < 0.1
    assert "DİKKAT" in r["chance_rate_note"]


def test_two_sync_moves_is_chance_level():
    r = call("co_movement", {"track_ids": ["T0122", "T0020"]})
    pair = r["pairs"][0]
    assert pair["relation"] == "met_at_end" and pair["chance_rate"] > 0.3


def test_co_movement_limits():
    assert "error" in call("co_movement", {"track_ids": ["T0019"]})
    assert "error" in call("co_movement", {"track_ids": ["T0019", "T0019"]})   # tekrar eden id tek sayılır


# ---------------------------------------------------------------- inspect_image (ağsız kısım)

def test_crop_targets():
    from backend.engine.agent.tools.image_tools import _target_box, render_crop
    box, desc = _target_box("img_006388", "track:T0057", None, None)
    assert box == (1295.0, 49.0, 24.0, 17.0) and "aday" in desc      # eşik altı aday kutusu
    data, crop = render_crop("img_000267", _target_box("img_000267", "img_000267_003", None, None)[0])
    assert data[:2] == b"\xff\xd8" and crop[0] < 834 < crop[2]            # JPEG, hedef kırpmanın içinde
    assert "error" in call("inspect_image", {"image_id": "img_000267", "question": "?",
                                             "vehicle_id": "img_006388_000"})   # başka görüntünün aracı
    assert "error" in call("inspect_image", {"image_id": "img_000267", "question": "?"})  # hedef yok

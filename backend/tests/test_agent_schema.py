"""Agent çıktı şeması, mesaj kurucu ve Step 8 kanıt dosyası ekleri (ağsız)."""

import copy

import pytest

from backend.engine.agent.prompts import build_messages, repair_message
from backend.engine.agent.schemas import fallback, finalize, validate
from backend.engine.analysis.consistency import build_context
from backend.engine.analysis.dossier import build_all, build_dossier
from backend.engine.data.repository import get_repository
from backend.engine.reports.claim_parser import parse_all


@pytest.fixture(scope="module")
def ctx():
    repo = get_repository()
    return build_context(repo, claims=parse_all(repo.reports(), repo.zones, mode="rules"))


@pytest.fixture(scope="module")
def dossier(ctx):
    return build_dossier("img_000267", ctx)


def _valid(dossier):
    medium = [v for v in dossier.vehicles if v.baseline_risk.level.value in ("critical", "high", "medium")]
    return {
        "overall_risk": "medium",
        "summary": "Doğu Yolu'nda 2 saattir duran bir kamyon; hakkındaki ikmal iddiası çelişkili.",
        "vehicles": [{"vehicle_id": v.vehicle_id, "risk_level": v.baseline_risk.level.value, "override_reason": None,
                      "rationale": "temel seviye uygun", "evidence": [f"det:{v.vehicle_id}"]} for v in medium],
        "attention_items": [{"title": "Gözlemle çelişen ikmal iddiası", "risk_level": "medium",
                             "rationale": "R083 otomobil diyor, orada duran kamyon var.",
                             "evidence": ["report:R083", "track:T0045"]}],
        "report_notes": [{"report_id": "R083", "verdict": "unreliable", "note": "tip ve hareket çelişiyor"}],
    }


def test_valid_output_passes(dossier):
    assert validate(_valid(dossier), dossier) == []


def test_upgrade_on_ruled_out_signal_rejected(dossier):
    out = copy.deepcopy(_valid(dossier))
    v = out["vehicles"][0]
    v.update(risk_level="critical", override_reason="Araçlar son adımda bir araya geliyor, chance_rate düşük.")
    assert any("elenmiş" in e for e in validate(out, dossier))
    v.update(override_reason="Görsel teyit: yüklü kamyon; son adımda bir araya geliyor.")
    assert not any("elenmiş" in e for e in validate(out, dossier))


@pytest.mark.parametrize("mutate, expected", [
    (lambda o: o["vehicles"].pop(0), "yok"),                                            # medium araç atlandı
    (lambda o: o["vehicles"][0].update(risk_level="critical"), "override_reason"),     # gerekçesiz sapma
    (lambda o: o["vehicles"][0].update(evidence=["det:img_999"]), "veride yok"),
    (lambda o: o["vehicles"][0].update(evidence=["T0045"]), "biçimi"),
    (lambda o: o.update(overall_risk="low"), "overall_risk"),
    (lambda o: o["report_notes"].append({"report_id": "R999", "verdict": "reliable"}), "report_id"),
    (lambda o: o["vehicles"].append({"vehicle_id": "img_nope", "risk_level": "low"}), "kanıt dosyasında yok"),
])
def test_invalid_outputs(dossier, mutate, expected):
    out = copy.deepcopy(_valid(dossier))
    mutate(out)
    errors = validate(out, dossier)
    assert any(expected in e for e in errors), errors


def test_finalize_fills_every_vehicle(dossier):
    result = finalize(_valid(dossier), dossier, {"iterations": 1})
    assert len(result["vehicles"]) == len(dossier.vehicles)
    assert {v["source"] for v in result["vehicles"]} == {"agent", "baseline"}


def test_fallback(dossier):
    result = fallback(dossier, {"iterations": 0}, "test")
    assert result["trace"]["fallback"] and result["trace"]["fallback_reason"] == "test"
    assert result["overall_risk"] == dossier.max_risk.value
    assert len(result["vehicles"]) == len(dossier.vehicles)
    assert all(v["source"] == "baseline" for v in result["vehicles"])


def test_messages_compact_and_complete(ctx):
    for d in build_all(ctx).values():
        msgs, prompt = build_messages(d)
        assert msgs[0]["role"] == "system" and "{{" not in msgs[0]["content"]
        user = msgs[1]["content"]
        assert len(user) < 16000                        # ~5k token altı
        assert all(v.vehicle_id in user for v in d.vehicles)
    assert "Hataları düzeltip" in repair_message(["x"])["content"]


# ---------------------------------------------------------------- Step 8 kanıt dosyası ekleri

def test_missed_vehicles_have_candidates(ctx):
    missed = [v for d in build_all(ctx).values() for v in d.vehicles if "possible_missed_detection" in v.flags]
    assert len(missed) == 4
    assert all(v.candidates and v.bbox_xywh == v.candidates[0].bbox_xywh for v in missed)
    assert all(c.confidence < 0.1 for v in missed for c in v.candidates)


def test_no_chance_level_coordination_anomalies(ctx):
    types = {a.type for d in build_all(ctx).values() for a in d.anomalies}
    assert "coordinated_arrival" not in types


def test_global_context(ctx):
    g = build_dossier("img_000860", ctx).global_context
    assert g["time"] == "14:10" and g["consistent_approachers"] >= 2
    assert {"T0020", "T0122"} <= set(g["by_zone"]["Dogu Yolu"]["tracks"])


def test_consistent_approach_guardrail_ignores_negations():
    from backend.engine.agent.schemas import _claims_consistent_approach as f
    assert f("tüm hareketlerinde tutarlı yaklaşan en hızlı araç")
    assert f("genel eğilim tutarlı yaklaşma; üsse 1,6 km")
    assert not f("Tutarlı yaklaşma işareti yok; temel skor korunuyor")
    assert not f("tutarlı yaklaşma değil, yalnızca yaklaşıyor")
    assert not f("hareketleri tutarlı yaklaşma sayılmaz")


def test_consistent_guardrail_in_free_text():
    from backend.engine.agent.schemas import _misused_consistent as f
    assert f("T0011 üsse tutarlı yaklaşıyor.", {"T0122"}) == ["T0011"]
    assert f("T0122 tutarlı yaklaşan kamyon; T0092 ise yalnızca yaklaşıyor.", {"T0122"}) == []
    assert f("T0092 için tutarlı yaklaşma işareti yok.", {"T0122"}) == []


def test_normalize_refs_and_fake_word(dossier):
    from backend.engine.agent.schemas import normalize_refs
    out = _valid(dossier)
    out["vehicles"][0]["evidence"] = [f"image:{out['vehicles'][0]['vehicle_id']}", "T0045"]
    normalize_refs(out)
    assert out["vehicles"][0]["evidence"] == [f"det:{out['vehicles'][0]['vehicle_id']}", "track:T0045"]
    assert validate(out, dossier) == []
    out["summary"] = "R083 sahte bir ikmal iddiası."
    assert any("sahte" in e for e in validate(out, dossier))


def test_consistent_guard_attributes_to_following_track():
    from backend.engine.agent.schemas import _misused_consistent
    text = "T0057 tespiti doğrulanamadı ve R002 derken tutarlı yaklaşan T0184'ü görmezden geliyor."
    assert _misused_consistent(text, {"T0184"}) == []
    assert _misused_consistent("T0057 tutarlı yaklaşma gösteriyor.", {"T0184"}) == ["T0057"]

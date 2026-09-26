from pathlib import Path

from dss.agent.validator import validate
from dss.schemas import Decision, EvidencePack

ROOT = Path(__file__).parents[1]
EX = ROOT / "eval" / "examples"


def _load():
    pack = EvidencePack.model_validate_json((EX / "example_evidence_pack.json").read_text(encoding="utf-8"))
    dec = Decision.model_validate_json((EX / "example_decision.json").read_text(encoding="utf-8"))
    return pack, dec


def test_example_decision_passes_validator():
    pack, dec = _load()
    assert validate(dec, pack) == []


def test_floor_violation_is_caught():
    pack, dec = _load()
    bad = dec.model_copy(update={"attention_level": "DUSUK", "attention_required": False})
    assert any("alt sınır" in e for e in validate(bad, pack))


def test_builder_runs_on_real_data():
    from dss.evidence.builder import Data, build_pack
    pack = build_pack(Data(ROOT / "data"), "img_003839", [])
    assert pack.image.capture_time == "13:25" and len(pack.reports) > 0

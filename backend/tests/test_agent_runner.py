"""Agent döngüsü: sahte LLM istemcisiyle (ağsız) tüm yollar."""

import json

import pytest

from backend.config import settings
from backend.engine import pipeline
from backend.engine.agent.runner import run_agent
from backend.engine.llm.client import BudgetExceeded, LLMResult, ToolCall


def _res(content="", tool_calls=None, finish="stop"):
    return LLMResult(content=content, reasoning="", tool_calls=tool_calls or [], finish_reason=finish,
                     prompt_tokens=100, completion_tokens=50, reasoning_tokens=10, cost_usd=0.001, latency_s=0.1)


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, **kw):
        self.calls.append({"messages": [dict(m) for m in messages], **kw})
        step = self.script.pop(0) if self.script else self._last
        self._last = step
        if isinstance(step, Exception):
            raise step
        return step(messages, kw) if callable(step) else step


@pytest.fixture(scope="module")
def dossier():
    return pipeline.build_dossier("img_000267")


def _valid_json(dossier) -> str:
    important = [v for v in dossier.vehicles if v.baseline_risk.level.value in ("critical", "high", "medium")]
    return json.dumps({
        "overall_risk": dossier.max_risk.value,
        "summary": "Durağan kamyon ve çelişkili ikmal iddiası.",
        "vehicles": [{"vehicle_id": v.vehicle_id, "risk_level": v.baseline_risk.level.value,
                      "override_reason": None, "rationale": "temel uygun", "evidence": [f"det:{v.vehicle_id}"]}
                     for v in important],
        "attention_items": [], "report_notes": [],
    }, ensure_ascii=False)


def test_tool_call_then_answer(dossier):
    tool = ToolCall("c1", "co_movement", json.dumps({"track_ids": ["T0045", "T0066"]}))
    client = FakeClient([_res(tool_calls=[tool]), _res(_valid_json(dossier))])
    events = []
    out = run_agent(dossier, client=client, on_event=events.append)
    assert not out["trace"]["fallback"]
    assert out["trace"]["iterations"] == 2 and len(out["trace"]["tool_calls"]) == 1
    assert "waiting_together" in out["trace"]["tool_calls"][0]["summary"]
    # tool sonucu mesaj geçmişine doğru eklendi
    second = client.calls[1]["messages"]
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "c1"
    assert second[-2]["tool_calls"][0]["function"]["name"] == "co_movement"
    types = [e["type"] for e in events]
    assert types[0] == "start" and "tool_call" in types and "tool_result" in types and types[-1] == "done"
    assert out["trace"]["tokens"]["input"] == 200 and out["trace"]["cost_usd"] == 0.002


def test_repair_once(dossier):
    client = FakeClient([_res('{"overall_risk": "low"}'), _res(_valid_json(dossier))])
    out = run_agent(dossier, client=client)
    assert not out["trace"]["fallback"] and out["trace"]["repairs"] == 1
    assert "şema doğrulamasından geçmedi" in client.calls[1]["messages"][-1]["content"]


def test_fallback_after_second_invalid(dossier):
    client = FakeClient([_res("bozuk"), _res("yine bozuk")])
    out = run_agent(dossier, client=client)
    assert out["trace"]["fallback"] and "düzeltilemedi" in out["trace"]["fallback_reason"]
    assert len(out["vehicles"]) == len(dossier.vehicles)


def test_tool_budget_then_forced_json(dossier):
    tool = ToolCall("c", "vehicles_in_area", json.dumps(
        {"lat": 39.92, "lon": 32.89, "radius_m": 50, "time_from": "09:00", "time_to": "10:00"}))
    n = settings.agent.max_tool_calls
    assert n < settings.agent.max_iterations          # tool hakkı iterasyonlardan önce bitmeli
    client = FakeClient([_res(tool_calls=[tool])] * n + [_res(_valid_json(dossier))])
    out = run_agent(dossier, client=client)
    assert len(out["trace"]["tool_calls"]) == n and not out["trace"]["fallback"]
    last = client.calls[-1]
    assert last["tools"] is None and last["response_format"] == {"type": "json_object"}


def test_model_that_never_answers_falls_back(dossier):
    """Tool sunulmasa bile tool çağırmaya devam eden model: limit sonunda kural tabanlı sonuç."""
    tool = ToolCall("c", "co_movement", json.dumps({"track_ids": ["T0045", "T0066"]}))
    client = FakeClient([_res(tool_calls=[tool])])        # hep tool çağırır
    out = run_agent(dossier, client=client)
    assert out["trace"]["fallback"]
    assert out["trace"]["iterations"] == settings.agent.max_iterations
    assert len(out["trace"]["tool_calls"]) == settings.agent.max_tool_calls
    assert client.calls[-1]["tools"] is None              # son iterasyonda tool sunulmadı


def test_bad_tool_args_do_not_crash(dossier):
    tool = ToolCall("c", "vehicles_in_area", "{bozuk json")
    client = FakeClient([_res(tool_calls=[tool]), _res(_valid_json(dossier))])
    out = run_agent(dossier, client=client)
    assert not out["trace"]["fallback"]
    assert "error" in out["trace"]["tool_calls"][0]["summary"]


def test_client_errors_fall_back(dossier):
    out = run_agent(dossier, client=FakeClient([BudgetExceeded("fren")]))
    assert out["trace"]["fallback"] and "BudgetExceeded" in out["trace"]["fallback_reason"]


def test_pipeline_caches_by_prompt_version(dossier, tmp_path):
    client = FakeClient([_res(_valid_json(dossier))])
    first = pipeline.assess("img_000267", client=client, directory=tmp_path)
    assert (tmp_path / "img_000267.json").exists() and len(client.calls) == 1
    again = pipeline.assess("img_000267", client=client, directory=tmp_path)
    assert again == json.loads((tmp_path / "img_000267.json").read_text()) and len(client.calls) == 1
    pipeline.assess("img_000267", client=client, force=True, directory=tmp_path)
    assert len(client.calls) == 2
    assert pipeline.is_current(first)

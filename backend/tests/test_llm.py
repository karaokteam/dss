"""Ağ gerektirmeyen LLM altyapısı testleri (önbellek, prompt şablonu, sonuç ayrıştırma)."""

from dataclasses import asdict, replace

import pytest

from backend.config import settings
from backend.engine.llm.cache import DiskCache, make_key
from backend.engine.llm.client import LLMClient, LLMResult, LLMUnavailable, ToolCall, _result_from_dict
from backend.engine.llm.prompt_loader import render, template_variables


def _result(**kw) -> LLMResult:
    base = dict(content="", reasoning="", tool_calls=[], finish_reason="stop", prompt_tokens=1,
                completion_tokens=1, reasoning_tokens=0, cost_usd=0.0, latency_s=0.0)
    base.update(kw)
    return LLMResult(**base)


def test_cache_key_is_order_independent():
    assert make_key({"a": 1, "b": [1, 2]}) == make_key({"b": [1, 2], "a": 1})
    assert make_key({"a": 1}) != make_key({"a": 2})


def test_disk_cache_roundtrip(tmp_path):
    cache = DiskCache(tmp_path)
    key = make_key({"x": "ğüşıöç"})
    assert cache.get(key) is None
    cache.set(key, {"v": "ğüşıöç"})
    assert cache.get(key) == {"v": "ğüşıöç"}


def test_result_serialization_roundtrip():
    r = _result(content="ok", tool_calls=[ToolCall("c1", "get_track", '{"track_id": "T0045"}')])
    back = _result_from_dict(asdict(r))
    assert back == r
    assert back.tool_calls[0].parsed_arguments() == {"track_id": "T0045"}


def test_assistant_message_includes_tool_calls():
    msg = _result(tool_calls=[ToolCall("c1", "f", "{}")]).assistant_message()
    assert msg["role"] == "assistant"
    assert msg["tool_calls"][0]["function"]["name"] == "f"


def test_json_parsing_tolerates_fences():
    assert _result(content='```json\n{"a": 1}\n```').json() == {"a": 1}
    assert _result(content='{"a": 1}').json() == {"a": 1}
    assert _result(content='{"a": 1}`').json() == {"a": 1}          # gözlenen: sonda fazladan backtick
    assert _result(content='Sonuç: {"a": 1}').json() == {"a": 1}
    with pytest.raises(ValueError):
        _result(content='{"a": ').json()


def test_truncated_flag():
    assert _result(finish_reason="length").truncated


def test_client_requires_key():
    with pytest.raises(LLMUnavailable):
        LLMClient(cfg=replace(settings.llm, api_key=""))


def test_prompt_render(tmp_path):
    (tmp_path / "demo.md").write_text("Rapor: {{ text }} / saat {{time}} / JSON: {\"a\": 1}", encoding="utf-8")
    p = render("demo", directory=tmp_path, text="5 kamyon", time="09:45")
    assert p.text == 'Rapor: 5 kamyon / saat 09:45 / JSON: {"a": 1}'
    assert len(p.version) == 12
    assert template_variables("{{a}} {{ b }}") == {"a", "b"}
    with pytest.raises(KeyError, match="eksik"):
        render("demo", directory=tmp_path, text="x")
    with pytest.raises(KeyError, match="olmayan"):
        render("demo", directory=tmp_path, text="x", time="y", typo="z")
    with pytest.raises(FileNotFoundError):
        render("yok", directory=tmp_path)

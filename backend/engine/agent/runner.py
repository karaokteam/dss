"""Agent döngüsü: kanıt dosyası → GLM ⇄ tool'lar → doğrulanmış değerlendirme.

Güvenceler:
- İterasyon ve tool çağrısı üst sınırı (sonsuz döngü / bütçe koruması). Tool hakkı bittiğinde ya da son
  iterasyonda tool'lar sunulmaz ve JSON modu zorlanır; böylece model her zaman cevap verme fırsatı bulur.
- Şema hatasında modele bir kez düzeltme şansı verilir.
- Her türlü hata (bozuk yanıt, bütçe freni, ağ hatası, limit) kural tabanlı sonuca (Katman 1) düşer: sistem
  hiçbir durumda sonuçsuz kalmaz ve bu durum `trace.fallback` ile açıkça işaretlenir.
- Her adım `on_event` ile yayınlanır (API'de SSE ile canlı iz).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Callable

from backend.config import settings
from backend.engine.agent import tools as tool_registry
from backend.engine.agent.prompts import build_messages, repair_message
from backend.engine.agent.schemas import fallback, finalize, normalize_refs, validate
from backend.engine.models import ImageDossier

EventCallback = Callable[[dict], None]
_TOOL_RESULT_MAX_CHARS = 6000


def _summarize(value, limit: int = 240) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[:limit] + "…"


def run_agent(dossier: ImageDossier, client=None, on_event: EventCallback | None = None,
              reasoning_effort: str | None = None) -> dict:
    cfg = settings.agent
    emit = on_event or (lambda e: None)
    started = time.monotonic()
    messages, prompt = build_messages(dossier)
    trace = {
        "model": settings.llm.model, "prompt_version": prompt.version,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reasoning_effort": reasoning_effort or cfg.reasoning_effort,
        "iterations": 0, "tool_calls": [], "repairs": 0,
        "tokens": {"input": 0, "output": 0, "reasoning": 0}, "cost_usd": 0.0, "cached_calls": 0,
        "fallback": False,
    }

    def done(result: dict) -> dict:
        result["trace"]["duration_s"] = round(time.monotonic() - started, 1)
        result["trace"]["cost_usd"] = round(result["trace"]["cost_usd"], 6)
        emit({"type": "fallback" if result["trace"]["fallback"] else "done",
              "overall_risk": result["overall_risk"], "reason": result["trace"].get("fallback_reason")})
        return result

    emit({"type": "start", "image_id": dossier.image_id, "prompt_version": prompt.version})
    try:
        if client is None:
            from backend.engine.llm.client import get_client
            client = get_client()

        for iteration in range(1, cfg.max_iterations + 1):
            trace["iterations"] = iteration
            tools_left = cfg.max_tool_calls - len(trace["tool_calls"])
            offer_tools = tools_left > 0 and iteration < cfg.max_iterations
            emit({"type": "llm", "iteration": iteration, "tools_offered": offer_tools})
            result = client.chat(
                messages,
                tools=tool_registry.get_tools() if offer_tools else None,
                response_format=None if offer_tools else {"type": "json_object"},
                reasoning_effort=trace["reasoning_effort"],
                max_tokens=16000,
                purpose=f"agent:{dossier.image_id}:{iteration}",
            )
            trace["tokens"]["input"] += result.prompt_tokens
            trace["tokens"]["output"] += result.completion_tokens
            trace["tokens"]["reasoning"] += result.reasoning_tokens
            trace["cost_usd"] += result.cost_usd
            trace["cached_calls"] += int(result.cached)
            if result.reasoning:
                emit({"type": "reasoning", "iteration": iteration, "text": _summarize(result.reasoning, 600)})

            if result.tool_calls:
                messages.append(result.assistant_message())
                for call in result.tool_calls:
                    if len(trace["tool_calls"]) >= cfg.max_tool_calls:
                        output = {"error": "tool çağrı limiti doldu; artık yalnızca son JSON'u döndür"}
                    else:
                        emit({"type": "tool_call", "iteration": iteration, "tool": call.name,
                              "args": _summarize(call.arguments, 400)})
                        output = tool_registry.call(call.name, call.arguments)
                        trace["tool_calls"].append({"iteration": iteration, "tool": call.name,
                                                    "args": call.arguments, "summary": _summarize(output)})
                        emit({"type": "tool_result", "iteration": iteration, "tool": call.name,
                              "summary": _summarize(output), "error": "error" in output})
                    content = json.dumps(output, ensure_ascii=False)
                    if len(content) > _TOOL_RESULT_MAX_CHARS:
                        content = content[:_TOOL_RESULT_MAX_CHARS] + '…"(kısaltıldı)"'
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
                continue

            # ---- son yanıt
            try:
                raw = normalize_refs(result.json())
                errors = validate(raw, dossier)
            except ValueError as e:
                raw, errors = None, [f"yanıt JSON olarak ayrıştırılamadı ({e})"
                                     + (" — max_tokens düşünmeye yetmedi" if result.truncated else "")]
            if not errors:
                return done(finalize(raw, dossier, trace))
            if trace["repairs"] >= 1:
                return done(fallback(dossier, trace, "şema hatası düzeltilemedi: " + "; ".join(errors[:3])))
            trace["repairs"] += 1
            emit({"type": "repair", "iteration": iteration, "errors": errors[:10]})
            messages.append(result.assistant_message())
            messages.append(repair_message(errors))

        return done(fallback(dossier, trace, f"iterasyon limiti ({cfg.max_iterations}) aşıldı"))
    except Exception as e:  # bütçe freni, ağ hatası, anahtar yok...
        return done(fallback(dossier, trace, f"{type(e).__name__}: {e}"))

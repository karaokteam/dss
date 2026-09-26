"""GLM istemcisi. Görev: LLM-1 · Açık konu: OI-LLM-2

OpenAI SDK + base_url. Gateway notları (gorev_tanimi.pdf):
- Düşünce `message.reasoning_content`'te, cevap `message.content`'te.
- `thinking` parametresi GÖNDERİLMEZ; `reasoning_effort` kullanılır.
- `max_tokens` düşünmeyi de kapsar → cömert (config.LLM_MAX_TOKENS).
- 429 → backoff; aynı anda en fazla 4 istek.
"""

from typing import Literal


def chat(
    messages: list[dict],
    effort: Literal["low", "high", "max"] = "low",
    tools: list[dict] | None = None,
) -> dict:
    """Ham assistant mesajını dict olarak döndürür (content, tool_calls). Yanıtlar cache/llm/ altında cache'lenir."""
    raise NotImplementedError

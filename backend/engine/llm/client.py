"""GLM gateway istemcisi (OpenAI uyumlu, LiteLLM).

Sağladıkları:
- Eşzamanlılık (4) ve dakikalık istek (60) limitlerine uyum; 429/5xx'te SDK'nın üstel geri çekilmeli tekrarı.
- Disk önbelleği: aynı istek ikinci kez ücretlendirilmez.
- Maliyet takibi: gateway her yanıtta istek maliyetini ve anahtarın toplam harcamasını header'da döner.
- Bütçe freni: toplam harcama `budget_stop_usd`'ye ulaşınca yeni istek atılmaz.
- Kullanım logu: outputs/logs/llm_usage.jsonl
"""

from __future__ import annotations

import base64
import json
import threading
import time
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from backend.config import LLMConfig, settings
from backend.engine.llm.cache import DiskCache, make_key


class LLMUnavailable(RuntimeError):
    """API anahtarı/URL yapılandırılmamış."""


class BudgetExceeded(RuntimeError):
    """Bütçe freni devrede."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str   # ham JSON metni; ayrıştırma çağıranın işi (bozuk JSON'u agent ele alır)

    def parsed_arguments(self) -> dict:
        return json.loads(self.arguments or "{}")


@dataclass
class LLMResult:
    content: str
    reasoning: str
    tool_calls: list[ToolCall]
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cost_usd: float
    latency_s: float
    cached: bool = False
    key_spend_usd: float | None = None
    meta: dict = field(default_factory=dict)

    @property
    def truncated(self) -> bool:
        """max_tokens düşünmeye yetmedi: içerik boş/yarım olabilir."""
        return self.finish_reason == "length"

    def assistant_message(self) -> dict:
        """Agent döngüsünde mesaj geçmişine eklenecek asistan mesajı."""
        msg: dict = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [{"id": c.id, "type": "function",
                                  "function": {"name": c.name, "arguments": c.arguments}}
                                 for c in self.tool_calls]
        return msg

    def json(self) -> dict:
        """İçerikteki ilk JSON nesnesini ayrıştırır. ```json çitlerini ve sondaki fazlalığı
        (ör. modelin eklediği tek bir "`") tolere eder; JSON'un kendisi bozuksa hata verir."""
        text = self.content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[4:] if text.lower().startswith("json") else text
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=0)
        value, _ = json.JSONDecoder().raw_decode(text, start)
        return value


class _RateLimiter:
    """Kayan pencere: son 60 saniyede en fazla N istek."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._times and now - self._times[0] >= 60:
                    self._times.popleft()
                if len(self._times) < self.per_minute:
                    self._times.append(now)
                    return
                wait = 60 - (now - self._times[0]) + 0.05
            time.sleep(wait)


class LLMClient:
    def __init__(self, cfg: LLMConfig | None = None, cache_dir: Path | None = None,
                 log_path: Path | None = None):
        self.cfg = cfg or settings.llm
        if not self.cfg.enabled:
            raise LLMUnavailable("LLM_API_KEY / LLM_BASE_URL .env dosyasında tanımlı değil.")
        self._client = OpenAI(base_url=self.cfg.base_url, api_key=self.cfg.api_key,
                              max_retries=self.cfg.max_retries, timeout=self.cfg.timeout_s)
        self._cache = DiskCache(cache_dir or settings.paths.llm_cache)
        self._log_path = log_path or settings.paths.logs / "llm_usage.jsonl"
        self._slots = threading.BoundedSemaphore(self.cfg.max_concurrency)
        self._rate = _RateLimiter(self.cfg.requests_per_minute)
        self._lock = threading.Lock()
        self._key_spend: float | None = None
        self.session_cost_usd = 0.0
        self.session_requests = 0

    # ------------------------------------------------------------ ana çağrı
    def chat(self, messages: list[dict], *, tools: list[dict] | None = None,
             response_format: dict | None = None, reasoning_effort: str | None = None,
             max_tokens: int | None = None, purpose: str = "", use_cache: bool = True) -> LLMResult:
        params = {
            "model": self.cfg.model,
            "messages": messages,
            "max_tokens": max_tokens or self.cfg.max_tokens,
        }
        if tools:
            params["tools"] = tools
        if response_format:
            params["response_format"] = response_format
        if reasoning_effort:
            params["reasoning_effort"] = reasoning_effort

        key = make_key(params)
        if use_cache:
            hit = self._cache.get(key)
            if hit is not None:
                result = _result_from_dict(hit)
                result.cached, result.cost_usd, result.latency_s = True, 0.0, 0.0
                self._log(purpose, key, result)
                return result

        self._check_budget()
        with self._slots:
            self._rate.acquire()
            started = time.monotonic()
            raw = self._client.chat.completions.with_raw_response.create(**params)
            latency = time.monotonic() - started
        response = raw.parse()
        result = _result_from_response(response, raw.headers, latency)

        with self._lock:
            self.session_cost_usd += result.cost_usd
            self.session_requests += 1
            if result.key_spend_usd is not None:
                self._key_spend = result.key_spend_usd
        # Yarım yanıtları önbelleğe alma: max_tokens artırılınca tekrar denenebilsin
        if use_cache and not result.truncated:
            self._cache.set(key, asdict(result))
        self._log(purpose, key, result)
        return result

    # ------------------------------------------------------------ bütçe
    def key_info(self) -> dict:
        """Gateway'den harcama ve bütçe (`/key/info`)."""
        url = self.cfg.base_url.rstrip("/").removesuffix("/v1") + "/key/info"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.cfg.api_key}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            info = json.load(resp)
        info = info.get("info", info)
        spend, budget = float(info.get("spend") or 0.0), info.get("max_budget")
        with self._lock:
            self._key_spend = spend
        return {
            "spend_usd": round(spend, 6),
            "max_budget_usd": budget,
            "remaining_usd": round(budget - spend, 6) if budget is not None else None,
            "budget_stop_usd": self.cfg.budget_stop_usd,
            "session_cost_usd": round(self.session_cost_usd, 6),
            "session_requests": self.session_requests,
        }

    def _check_budget(self) -> None:
        if self._key_spend is None:
            try:
                self.key_info()
            except OSError:
                return   # bütçe sorgulanamadı: isteği engelleme, header'dan öğrenilecek
        if self._key_spend is not None and self._key_spend >= self.cfg.budget_stop_usd:
            raise BudgetExceeded(
                f"Harcama {self._key_spend:.2f} USD, fren eşiği {self.cfg.budget_stop_usd:.2f} USD.")

    # ------------------------------------------------------------ log
    def _log(self, purpose: str, key: str, r: LLMResult) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "purpose": purpose, "key": key[:16], "cached": r.cached,
            "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
            "reasoning_tokens": r.reasoning_tokens, "cost_usd": r.cost_usd,
            "latency_s": round(r.latency_s, 2), "finish_reason": r.finish_reason,
        }
        with self._lock:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- yardımcılar

def image_part(data: bytes, mime: str = "image/jpeg") -> dict:
    """Vision için mesaj içeriğine eklenecek görüntü bloğu."""
    b64 = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def _float_header(headers, name: str) -> float | None:
    try:
        return float(headers.get(name))
    except (TypeError, ValueError):
        return None


def _result_from_response(response, headers, latency: float) -> LLMResult:
    choice = response.choices[0]
    msg = choice.message
    extra = msg.model_extra or {}
    usage = response.usage
    details = getattr(usage, "completion_tokens_details", None)
    return LLMResult(
        content=msg.content or "",
        reasoning=extra.get("reasoning_content") or "",
        tool_calls=[ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "")
                    for c in (msg.tool_calls or [])],
        finish_reason=choice.finish_reason or "",
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        reasoning_tokens=(getattr(details, "reasoning_tokens", 0) or 0) if details else 0,
        cost_usd=_float_header(headers, "x-litellm-response-cost") or 0.0,
        latency_s=latency,
        key_spend_usd=_float_header(headers, "x-litellm-key-spend"),
    )


def _result_from_dict(d: dict) -> LLMResult:
    d = dict(d)
    d["tool_calls"] = [ToolCall(**c) for c in d.get("tool_calls", [])]
    return LLMResult(**d)


@lru_cache(maxsize=1)
def get_client() -> LLMClient:
    """Uygulama genelinde tek istemci (limitler süreç genelinde paylaşılsın)."""
    return LLMClient()

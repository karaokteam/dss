"""Tool kaydı ve çağırma. OpenAI-uyumlu tool şeması üretir."""

import json
from collections.abc import Callable
from typing import Any

TOOLS: dict[str, dict[str, Any]] = {}


def tool(name: str, description: str, parameters: dict | None = None):
    def deco(fn: Callable[..., Any]):
        TOOLS[name] = {
            "fn": fn,
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters or {"type": "object", "properties": {}},
                },
            },
        }
        return fn

    return deco


def schemas() -> list[dict]:
    return [t["schema"] for t in TOOLS.values()]


def dispatch(name: str, arguments: str | dict) -> Any:
    if name not in TOOLS:
        return {"error": f"bilinmeyen tool: {name}"}
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    try:
        return TOOLS[name]["fn"](**args)
    except Exception as e:  # LLM'e hatayı metin olarak döndür, döngü kırılmasın
        return {"error": f"{type(e).__name__}: {e}"}

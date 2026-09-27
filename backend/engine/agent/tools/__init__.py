"""Agent tool registry.

İlke: tool yalnızca agent'ın BELİRSİZ bir durumda kendi kararıyla soruşturma yapacağı yerlerde vardır
(nereye, ne zaman, hangi yarıçapta bakılacağı ya da hangi hipotezin sınanacağı metinden/kanıttan
çıkarsanmalıdır). Deterministik olarak hesaplanabilen her şey zaten kanıt dosyasındadır (dossier).

Yeni tool eklemek: modülde fonksiyonu `@tool` ile işaretle ve modülü aşağıdaki import listesine ekle.
Şema; tip ipuçlarından ve docstring'deki "Args:" bölümünden üretilir.
"""

from __future__ import annotations

import inspect
import json
import re
import types
import typing
from dataclasses import dataclass
from typing import Any, Callable, Literal


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., dict]

    def schema(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


_REGISTRY: dict[str, ToolSpec] = {}


class ToolArgumentError(ValueError):
    pass


# ---------------------------------------------------------------- şema üretimi

def _json_type(tp) -> dict:
    origin = typing.get_origin(tp)
    if origin is Literal:
        values = typing.get_args(tp)
        return {"type": "string", "enum": list(values)}
    if origin in (list, tuple):
        (item,) = typing.get_args(tp)[:1] or (str,)
        return {"type": "array", "items": _json_type(item)}
    if origin in (typing.Union, types.UnionType):
        inner = [a for a in typing.get_args(tp) if a is not type(None)]
        return _json_type(inner[0])
    return {str: {"type": "string"}, int: {"type": "integer"}, float: {"type": "number"},
            bool: {"type": "boolean"}}.get(tp, {"type": "string"})


def _parse_docstring(doc: str) -> tuple[str, dict[str, str]]:
    doc = inspect.cleandoc(doc or "")
    head, _, args = doc.partition("Args:")
    params = {}
    for m in re.finditer(r"^\s{2,}(\w+):\s*(.+?)(?=^\s{2,}\w+:|\Z)", args, re.M | re.S):
        params[m[1]] = " ".join(m[2].split())
    return " ".join(head.split()), params


def spec_of(fn: Callable[..., dict]) -> ToolSpec:
    """Fonksiyondan ToolSpec üretir (kaydetmeden). Başka registry'ler (ör. chatbot) de kullanır."""
    hints = typing.get_type_hints(fn)
    description, docs = _parse_docstring(fn.__doc__)
    props, required = {}, []
    for name, param in inspect.signature(fn).parameters.items():
        prop = _json_type(hints.get(name, str))
        if name in docs:
            prop["description"] = docs[name]
        props[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return ToolSpec(
        name=fn.__name__, description=description, fn=fn,
        parameters={"type": "object", "properties": props, "required": required, "additionalProperties": False},
    )


def tool(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Analiz agent'ının registry'sine kaydeder."""
    _REGISTRY[fn.__name__] = spec_of(fn)
    return fn


# ---------------------------------------------------------------- çağırma

def _coerce(value: Any, prop: dict, name: str) -> Any:
    t = prop.get("type")
    try:
        if t == "integer":
            if isinstance(value, bool):
                raise TypeError
            f = float(value)
            if f != int(f):
                raise ValueError
            return int(f)
        if t == "number":
            if isinstance(value, bool):
                raise TypeError
            return float(value)
        if t == "boolean":
            if isinstance(value, bool):
                return value
            raise TypeError
        if t == "array":
            if not isinstance(value, list):
                raise TypeError
            return [_coerce(v, prop["items"], name) for v in value]
        if t == "string":
            value = str(value)
            if "enum" in prop and value not in prop["enum"]:
                raise ToolArgumentError(f"{name}: {value!r} geçersiz; seçenekler: {prop['enum']}")
            return value
    except (TypeError, ValueError) as e:
        if isinstance(e, ToolArgumentError):
            raise
        raise ToolArgumentError(f"{name}: {t} bekleniyordu, {value!r} geldi") from None
    return value


def call(name: str, arguments: dict | str | None) -> dict:
    """Tool'u çağırır. Hiçbir durumda exception fırlatmaz; hata agent'a {"error": ...} olarak döner."""
    return invoke(_REGISTRY, name, arguments)


def invoke(registry_: dict[str, ToolSpec], name: str, arguments: dict | str | None) -> dict:
    spec = registry_.get(name)
    if spec is None:
        return {"error": f"Bilinmeyen tool: {name}. Mevcut: {sorted(registry_)}"}
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
        if not isinstance(args, dict):
            raise ToolArgumentError("argümanlar bir JSON nesnesi olmalı")
        props = spec.parameters["properties"]
        unknown = set(args) - set(props)
        if unknown:
            raise ToolArgumentError(f"bilinmeyen argüman(lar): {sorted(unknown)}")
        missing = [p for p in spec.parameters["required"] if args.get(p) is None]
        if missing:
            raise ToolArgumentError(f"eksik argüman(lar): {missing}")
        clean = {k: _coerce(v, props[k], k) for k, v in args.items() if v is not None}
        return spec.fn(**clean)
    except json.JSONDecodeError as e:
        return {"error": f"argümanlar JSON değil: {e}"}
    except (ToolArgumentError, KeyError, ValueError) as e:
        return {"error": str(e).strip("'")}
    except Exception as e:  # tool hatası agent döngüsünü düşürmemeli
        return {"error": f"{type(e).__name__}: {e}"}


def get_tools(names: list[str] | None = None) -> list[dict]:
    specs = _REGISTRY.values() if names is None else [_REGISTRY[n] for n in names]
    return [s.schema() for s in specs]


def registry() -> dict[str, ToolSpec]:
    return dict(_REGISTRY)


# Tool modülleri (import edilince @tool ile kaydolur)
from backend.engine.agent.tools import area_tools, image_tools, movement_tools  # noqa: E402,F401

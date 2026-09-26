"""Sohbet tool'ları. Bu klasördeki her .py dosyası otomatik yüklenir.

Yeni tool: kendi dosyana `@tool(...)` ile fonksiyon ekle — başka yere dokunma.
"""

import importlib
import pkgutil

from agent.chat.tools.registry import TOOLS, dispatch, schemas, tool

__all__ = ["TOOLS", "dispatch", "schemas", "tool"]

for _m in pkgutil.iter_modules(__path__):
    if _m.name != "registry":
        importlib.import_module(f"{__name__}.{_m.name}")

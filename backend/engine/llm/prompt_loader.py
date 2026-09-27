"""`backend/prompts/*.md` şablonlarını yükler ve `{{değişken}}` yer tutucularını doldurur.

Prompt metni koddan ayrıdır; davranış iyileştirmesi yalnızca .md dosyası değiştirilerek yapılır.
Her prompt'un içerik hash'i çıktıların `trace`'ine yazılır (hangi versiyonla üretildiği izlenir).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from backend.config import settings

_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    text: str
    version: str   # şablonun (doldurulmadan önceki) içerik hash'i, 12 karakter


def _template_path(name: str, directory: Path | None) -> Path:
    return (directory or settings.paths.prompts) / f"{name}.md"


def load_template(name: str, directory: Path | None = None) -> str:
    path = _template_path(name, directory)
    if not path.exists():
        raise FileNotFoundError(f"Prompt şablonu yok: {path}")
    return path.read_text(encoding="utf-8")


def template_variables(template: str) -> set[str]:
    return set(_VAR.findall(template))


def render(name: str, directory: Path | None = None, **variables) -> Prompt:
    """Şablonu doldurur. Eksik değişken hata verir; şablonda olmayan değişken de (yazım hatasını yakalamak için)."""
    template = load_template(name, directory)
    needed = template_variables(template)
    missing = needed - variables.keys()
    extra = variables.keys() - needed
    if missing:
        raise KeyError(f"{name}: eksik değişken(ler): {sorted(missing)}")
    if extra:
        raise KeyError(f"{name}: şablonda olmayan değişken(ler): {sorted(extra)}")
    text = _VAR.sub(lambda m: str(variables[m.group(1)]), template)
    version = hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]
    return Prompt(name=name, text=text, version=version)

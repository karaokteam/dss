"""LLM yanıtları için disk önbelleği. Aynı girdiye ikinci kez ödeme yapılmaz; sonuçlar tekrarlanabilir olur."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


def make_key(payload: dict) -> str:
    """İstek içeriğinin (model, mesajlar, tool'lar, parametreler) kararlı sha256 özeti."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class DiskCache:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _path(self, key: str) -> Path:
        return self.directory / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None   # bozuk kayıt: önbellek ıskası say

    def set(self, key: str, value: dict) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Eşzamanlı yazımlarda yarım dosya kalmasın: geçici dosyaya yaz, atomik taşı
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
        os.replace(tmp, path)

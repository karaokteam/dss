"""Motorun dış kapısı. API ve CLI yalnızca bu modülü çağırır.

    build_dossier(image_id)       Katman 1 (LLM'siz, deterministik)
    assess(image_id, force=...)   Katman 2 (agent); sonuç outputs/assessments/<id>.json'da saklanır
    run_all(...)                  tüm görüntüler, eşzamanlı
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.config import settings
from backend.engine.agent.prompts import system_prompt
from backend.engine.agent.runner import EventCallback, run_agent
from backend.engine.analysis.consistency import get_context
from backend.engine.analysis.dossier import build_dossier as _build_dossier
from backend.engine.analysis.dossier import save_dossier
from backend.engine.models import ImageDossier

_dossiers: dict[str, ImageDossier] = {}
_lock = threading.Lock()
_image_locks: dict[str, threading.Lock] = {}


def build_dossier(image_id: str, save: bool = False) -> ImageDossier:
    """Kanıt dosyası (bellekte önbellekli; veri değişmediği sürece aynıdır)."""
    with _lock:
        cached = _dossiers.get(image_id)
    if cached is None:
        cached = _build_dossier(image_id, get_context())
        with _lock:
            _dossiers[image_id] = cached
    if save:
        save_dossier(cached)
    return cached


def _path(image_id: str, directory: Path | None) -> Path:
    return (directory or settings.paths.assessments) / f"{image_id}.json"


def load_assessment(image_id: str, directory: Path | None = None) -> dict | None:
    path = _path(image_id, directory)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def is_current(assessment: dict) -> bool:
    """Kayıtlı sonuç güncel prompt sürümüyle mi üretilmiş?"""
    return assessment.get("trace", {}).get("prompt_version") == system_prompt().version


def assess(image_id: str, force: bool = False, on_event: EventCallback | None = None,
           reasoning_effort: str | None = None, client=None, directory: Path | None = None) -> dict:
    """Görüntüyü değerlendirir. Güncel bir sonuç varsa (ve force yoksa) onu döner.
    Aynı görüntü için eşzamanlı çağrılar tek çalıştırmada birleşir."""
    with _lock:
        lock = _image_locks.setdefault(image_id, threading.Lock())
    with lock:
        existing = load_assessment(image_id, directory)
        if existing and not force and is_current(existing):
            if on_event:
                on_event({"type": "done", "overall_risk": existing["overall_risk"], "cached": True})
            return existing
        result = run_agent(build_dossier(image_id), client=client, on_event=on_event,
                           reasoning_effort=reasoning_effort)
        path = _path(image_id, directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        return result


def run_all(image_ids: list[str] | None = None, force: bool = False, workers: int | None = None,
            on_event: EventCallback | None = None, reasoning_effort: str | None = None,
            client=None) -> dict[str, dict]:
    ctx = get_context()   # iş parçacıklarından önce bağlamı bir kez kur
    ids = image_ids or [img.id for img in ctx.repo.images()]
    for image_id in ids:
        build_dossier(image_id)

    def one(image_id: str) -> tuple[str, dict]:
        cb = (lambda e: on_event({**e, "image_id": image_id})) if on_event else None
        return image_id, assess(image_id, force=force, on_event=cb, reasoning_effort=reasoning_effort,
                                client=client)

    with ThreadPoolExecutor(max_workers=workers or settings.llm.max_concurrency) as pool:
        return dict(pool.map(one, ids))

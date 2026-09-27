"""Arka plan analiz işleri: kuyruk, durum, ilerleme ve SSE için olay akışı.

Aynı görüntü kümesi için çalışan bir iş varsa yeni iş açılmaz, mevcut iş döner.
LLM eşzamanlılığı istemci tarafında süreç genelinde 4 ile sınırlı olduğundan birden fazla iş güvenle koşabilir.
"""

from __future__ import annotations

import itertools
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from backend.engine import pipeline

ACTIVE = ("queued", "running")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Job:
    def __init__(self, image_ids: list[str], force: bool, effort: str | None):
        self.id = "job_" + uuid.uuid4().hex[:8]
        self.image_ids, self.force, self.effort = image_ids, force, effort
        self.status = "queued"
        self.created_at, self.started_at, self.finished_at = _now(), None, None
        self.results: dict[str, str] = {}
        self.error: str | None = None
        self.events: list[dict] = []
        self._cond = threading.Condition()
        self._seq = itertools.count(1)

    def push(self, event: dict) -> None:
        with self._cond:
            e = {"id": next(self._seq), "ts": _now(), **event}
            self.events.append(e)
            if e["type"] in ("done", "fallback") and e.get("image_id"):
                self.results[e["image_id"]] = e.get("overall_risk")
            self._cond.notify_all()

    def to_dict(self) -> dict:
        return {
            "job_id": self.id, "status": self.status, "image_ids": self.image_ids, "force": self.force,
            "reasoning_effort": self.effort,
            "progress": {"done": len(self.results), "total": len(self.image_ids)},
            "results": self.results, "error": self.error,
            "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
            "events_url": f"/api/jobs/{self.id}/events",
            "assessment_urls": {i: f"/api/images/{i}/assessment" for i in self.image_ids},
        }

    def stream(self, after: int = 0, keepalive_s: float = 15.0):
        """(olay | None) üretir; None → canlı tut. İş bitip tüm olaylar gönderilince durur."""
        idx = next((i for i, e in enumerate(self.events) if e["id"] > after), len(self.events))
        while True:
            with self._cond:
                if idx >= len(self.events) and self.status in ACTIVE:
                    self._cond.wait(timeout=keepalive_s)
                pending = self.events[idx:]
                finished = self.status not in ACTIVE
            for e in pending:
                yield e
            idx += len(pending)
            if finished and idx >= len(self.events):
                return
            if not pending:
                yield None


class JobManager:
    def __init__(self, workers: int = 2, keep: int = 50):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="assess-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._keep = keep

    def submit(self, image_ids: list[str], force: bool = False, effort: str | None = None) -> tuple[Job, bool]:
        """(iş, yeni_mi). Aynı görüntü kümesi için aktif iş varsa onu döner."""
        key = sorted(set(image_ids))
        with self._lock:
            for job in self._jobs.values():
                if job.status in ACTIVE and sorted(set(job.image_ids)) == key:
                    return job, False
            job = Job(list(dict.fromkeys(image_ids)), force, effort)
            self._jobs[job.id] = job
            self._trim()
        self._pool.submit(self._run, job)
        return job, True

    def get(self, job_id: str) -> Job:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Bilinmeyen iş: {job_id}")
            return self._jobs[job_id]

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _run(self, job: Job) -> None:
        job.status, job.started_at = "running", _now()
        job.push({"type": "job_started", "total": len(job.image_ids)})
        started = time.monotonic()
        try:
            pipeline.run_all(job.image_ids, force=job.force, on_event=job.push, reasoning_effort=job.effort)
            job.status = "done"
        except Exception as e:   # run_agent kendi hatalarını yedeğe düşürür; buraya yalnızca beklenmeyenler gelir
            job.status, job.error = "failed", f"{type(e).__name__}: {e}"
        job.finished_at = _now()
        job.push({"type": "job_finished", "status": job.status, "duration_s": round(time.monotonic() - started, 1),
                  "results": job.results, "error": job.error})

    def _trim(self) -> None:
        done = [j for j in sorted(self._jobs.values(), key=lambda j: j.created_at) if j.status not in ACTIVE]
        for j in done[:max(0, len(self._jobs) - self._keep)]:
            self._jobs.pop(j.id, None)


_manager: JobManager | None = None
_manager_lock = threading.Lock()


def get_jobs() -> JobManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = JobManager()
        return _manager

"""8 adımlı sabit akış. Görevler: PIP-1 (run_events, run), PIP-2 (scan_all) · Adımlar: README "Pipeline"

Her adım try/except içinde çalışır; hata olursa status="error" event'i üretilir ve
mümkünse devam edilir (ör. rapor adımı çökerse risk raporsuz hesaplanır) → demo kırılmaz.

run_events: UI'ın izlediği PipelineEvent akışı.
run:        sadece sonucu isteyenler için (testler, chat tool'ları).
"""

from collections.abc import Iterator

from agent.schemas import ImageAssessment, PipelineEvent


def run_events(image_id: str) -> Iterator[PipelineEvent]:
    """Son event (name='brief', status='done') payload['assessment'] taşır."""
    raise NotImplementedError


def run(image_id: str) -> ImageAssessment:
    raise NotImplementedError


def scan_all(with_brief: bool = False) -> list[ImageAssessment]:
    raise NotImplementedError

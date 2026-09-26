"""Rapor → iddia, kural tabanlı (regex + lexicon). Görev: RAP-2

Koordinat ("39.9374N 32.8483E"), adet, araç türü, bölge adı, niyet (lexicon).
"""

from collections.abc import Callable

from agent.schemas import FieldReport, ReportClaim


def extract_regex(report: FieldReport) -> ReportClaim | None:
    """Çözemezse None."""
    raise NotImplementedError


def extract(
    reports: list[FieldReport], llm_fallback: Callable[[FieldReport], ReportClaim] | None = None
) -> list[ReportClaim]:
    """Önce regex; None dönen raporlar için llm_fallback (verilmişse, LLM-3), yoksa intent='neutral' boş iddia.
    Pipeline llm_fallback olarak llm_extraction.extract_llm'i geçer — bu dosya LLM'e bağımlı değildir."""
    raise NotImplementedError

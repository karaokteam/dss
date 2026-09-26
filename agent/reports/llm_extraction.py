"""Regex'in çözemediği raporlar için LLM çıkarımı. Görev: LLM-3 · Açık konu: OI-LLM-2

LLM yalnızca yapılandırılmış alan doldurur (sınıf, adet, konum, bölge, niyet); sayı hesaplamaz.
Sonuç cache'lenir (raporlar tek havuz). Prompt: agent/llm/prompts/report_extraction.md
"""

from agent.schemas import FieldReport, ReportClaim


def extract_llm(report: FieldReport) -> ReportClaim:
    raise NotImplementedError

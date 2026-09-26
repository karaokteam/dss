"""Gerekçeli brief. Görev: LLM-2

Girdi ImageAssessment'taki sayılar ve factors; LLM seviyeyi değiştiremez.
LLM erişilemezse template_brief ile deterministik metin üretilir (OI-SUN-1).
"""

from agent.schemas import Brief, ImageAssessment


def template_brief(assessment: ImageAssessment) -> Brief:
    raise NotImplementedError


def generate(assessment: ImageAssessment) -> Brief:
    raise NotImplementedError

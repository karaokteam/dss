"""Pipeline'ı saran tool'lar. Görev: LLM-4"""

from agent.chat.tools.registry import tool

_IMAGE = {"type": "object", "properties": {"image_id": {"type": "string"}}, "required": ["image_id"]}


@tool(
    "assess_image",
    "Bir drone görüntüsünü 8 adımlı pipeline ile değerlendirir, bulguları ve brief'i döndürür.",
    _IMAGE,
)
def assess_image(image_id: str) -> dict:
    raise NotImplementedError


@tool("scan_all", "Tüm görüntüleri değerlendirip risk seviyesine göre sıralı özet döndürür.")
def scan_all() -> list[dict]:
    raise NotImplementedError

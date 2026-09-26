"""Veri sorgulayan tool'lar. Görev: LLM-4"""

from agent.chat.tools.registry import tool


@tool("list_images", "Görüntü listesini çekim saati ve bölgesiyle döndürür.")
def list_images() -> list[dict]:
    raise NotImplementedError


@tool(
    "get_track",
    "Bir track'in son 2 saatlik noktalarını ve hareket özetini döndürür.",
    {"type": "object", "properties": {"track_id": {"type": "string"}}, "required": ["track_id"]},
)
def get_track(track_id: str) -> dict:
    raise NotImplementedError


@tool(
    "find_reports",
    "Saat aralığı veya bölgeye göre saha raporlarını ve doğrulama sonuçlarını döndürür.",
    {
        "type": "object",
        "properties": {
            "zone": {"type": "string"},
            "time_from": {"type": "string"},
            "time_to": {"type": "string"},
        },
    },
)
def find_reports(
    zone: str | None = None, time_from: str | None = None, time_to: str | None = None
) -> list[dict]:
    raise NotImplementedError

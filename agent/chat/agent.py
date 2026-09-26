"""Tool-calling döngüsü. Görev: LLM-5

Döngü: llm.client.chat(messages, tools=tools.schemas()) → tool_call varsa tools.dispatch → tekrar.
Sistem promptu: agent/llm/prompts/chat_system.md
"""


def reply(history: list[dict], user_message: str) -> tuple[str, list[dict]]:
    """(yanıt metni, güncellenmiş history)"""
    raise NotImplementedError

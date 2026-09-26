"""
Sahibi : Kişi 5 (Polat)
Görev  : OpenAI SDK ile GLM gateway: semaphore(4), retry, disk cache, bütçe koruması, reasoning_content

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    chat(messages, tools=None, effort='high') -> message
    budget() -> {'spend': float, 'max_budget': float}
"""

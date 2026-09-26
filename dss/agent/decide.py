"""
Sahibi : Kişi 5 (Polat)
Görev  : Karar döngüsü: EvidencePack -> LLM -> submit_assessment -> validator -> cache

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    decide(pack: EvidencePack) -> Decision
    assess(image_id) -> Decision   # uçtan uca; UI bunu çağırır
"""

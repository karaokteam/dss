"""
Sahibi : Kişi 2
Görev  : Çekim anındaki track'lerle Hungarian eşleştirme, eşleşmeyen track'lerin kare içi/dışı ayrımı

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    load_tracks() -> DataFrame[track_id, time, t, lat, lon, x, y, d]
    match(detections, capture_time) -> (matches, unmatched)
"""

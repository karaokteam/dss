"""
Sahibi : Kişi 2
Görev  : Piksel -> lat/lon -> üs merkezli metre düzlemi, bölge bulma, kuzey-hizalı kare kontrolü

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    pixel_to_latlon(px, py, meta) -> (lat, lon)
    to_local(lat, lon) -> (x_m, y_m)
    nearest_zone(lat, lon) -> str
    check_north_up(meta) -> list[str]
"""

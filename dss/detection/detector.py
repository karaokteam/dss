"""
Sahibi : Kişi 1
Görev  : 1. gün modeliyle 40 görüntüde tespit, eşik ayarı, JSON cache, araç kırpma (inspect_vehicle için)

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    detect(image_id: str) -> list[dict]        # [{'label','conf','box':(x,y,w,h),'lat','lon'}]
    crop(image_id: str, box, pad=0.3) -> bytes  # vision tool'u için JPEG
"""

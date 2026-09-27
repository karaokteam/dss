"""Koordinat ve mesafe hesapları.

Piksel ↔ koordinat dönüşümü görev tanımındaki (gorev_tanimi.pdf) doğrusal oranlamadır:
görüntü kuşbakışı ve perspektifi düzeltilmiş kabul edilir; pikselin görüntü içindeki oranı,
köşe koordinatları arasına aynı oranla uygulanır. Açı/mesafe ile projeksiyon yapılmaz.

Mesafeler kuş uçuşudur (haversine).
"""

from __future__ import annotations

import math

from backend.engine.models import Base, ImageMeta, LatLon

EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------- piksel ↔ koordinat

def pixel_to_latlon(image: ImageMeta, x: float, y: float) -> LatLon:
    """(x, y) pikseli (sol üst 0,0) → (lat, lon).

    boylam = sol_üst.boylam + (x / genişlik) × (sağ_üst.boylam − sol_üst.boylam)
    enlem  = sol_üst.enlem  + (y / yükseklik) × (sol_alt.enlem − sol_üst.enlem)
    """
    tl, tr, bl = image.corners.top_left, image.corners.top_right, image.corners.bottom_left
    lon = tl[1] + (x / image.width_px) * (tr[1] - tl[1])
    lat = tl[0] + (y / image.height_px) * (bl[0] - tl[0])
    return lat, lon


def latlon_to_pixel(image: ImageMeta, lat: float, lon: float) -> tuple[float, float]:
    """pixel_to_latlon'un tersi (track noktasını görüntü üzerine çizmek, kırpma vb. için)."""
    tl, tr, bl = image.corners.top_left, image.corners.top_right, image.corners.bottom_left
    x = (lon - tl[1]) / (tr[1] - tl[1]) * image.width_px
    y = (lat - tl[0]) / (bl[0] - tl[0]) * image.height_px
    return x, y


def bbox_center(bbox_xywh: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = bbox_xywh
    return x + w / 2, y + h / 2


# ---------------------------------------------------------------- kuş uçuşu mesafe / yön

def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası kuş uçuşu mesafe (metre, haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """1. noktadan 2. noktaya yön (0=kuzey, 90=doğu). Aracın gidiş yönü için kullanılır."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff_deg(a: float, b: float) -> float:
    """İki yön arasındaki en küçük fark (0–180)."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def dist_to_base_m(base: Base, lat: float, lon: float) -> float:
    return distance_m(lat, lon, base.lat, base.lon)


# ---------------------------------------------------------------- görüntü ayak izi

def in_footprint(image: ImageMeta, lat: float, lon: float) -> bool:
    (lat0, lat1), (lon0, lon1) = image.lat_bounds, image.lon_bounds
    return lat0 <= lat <= lat1 and lon0 <= lon <= lon1


def distance_to_footprint_m(image: ImageMeta, lat: float, lon: float) -> float:
    """Noktanın görüntü ayak izine kuş uçuşu uzaklığı (içerideyse 0)."""
    (lat0, lat1), (lon0, lon1) = image.lat_bounds, image.lon_bounds
    nearest_lat = min(max(lat, lat0), lat1)
    nearest_lon = min(max(lon, lon0), lon1)
    return distance_m(lat, lon, nearest_lat, nearest_lon)


def footprint_size_m(image: ImageMeta) -> tuple[float, float]:
    """(genişlik, yükseklik) metre."""
    (lat0, lat1), (lon0, lon1) = image.lat_bounds, image.lon_bounds
    mid_lat = (lat0 + lat1) / 2
    return distance_m(mid_lat, lon0, mid_lat, lon1), distance_m(lat0, lon0, lat1, lon0)

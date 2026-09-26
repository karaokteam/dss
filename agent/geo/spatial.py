"""Mesafe, yön, en yakın bölge — HAZIR (Step 0).

Birçok step bunu kullanır (TRK-1, TRK-2, RAP-3, RSK-1): imzaları değiştirmeyin.
"""

import math

from agent.schemas import LatLon, ZonesFile

EARTH_RADIUS_M = 6_371_000


def distance_m(a: LatLon, b: LatLon) -> float:
    """Haversine, metre."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    """a'dan b'ye yön; 0 = kuzey, 90 = doğu."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return math.degrees(math.atan2(y, x)) % 360


def nearest_zone(point: LatLon, zones: ZonesFile) -> str | None:
    if not zones.zones:
        return None
    return min(zones.zones, key=lambda z: distance_m(point, z.center)).name

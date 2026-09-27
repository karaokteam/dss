"""Bölge ataması ve metinde bölge adı bulma."""

from __future__ import annotations

import re
from functools import lru_cache

from backend.engine.geo.geometry import distance_m
from backend.engine.models import Zone

_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u", "â": "a", "î": "i", "û": "u",
})


def normalize_text(text: str) -> str:
    """Türkçe karakterleri sadeleştirir, küçük harfe çevirir, noktalamayı boşluğa indirir.
    "Güneybatı Yolu'nda" -> "guneybati yolu nda" """
    text = text.translate(_TR_MAP).lower()
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=None)
def _zone_pattern(name: str) -> re.Pattern:
    words = normalize_text(name).split()
    # Son kelimeye ek gelebilir: "Kuzey Yolu" -> "kuzey yolunda"; başta kelime sınırı,
    # böylece "Kuzey Yolu" "Kuzeybati Yolu" içinde eşleşmez.
    body = r"\s+".join(re.escape(w) for w in words)
    return re.compile(rf"\b{body}\w*")


def find_zones_in_text(text: str, zones: tuple[Zone, ...]) -> list[Zone]:
    """Metinde adı geçen bölgeler (metindeki sıraya göre)."""
    norm = normalize_text(text)
    found = []
    for z in zones:
        m = _zone_pattern(z.name).search(norm)
        if m:
            found.append((m.start(), z))
    return [z for _, z in sorted(found, key=lambda x: x[0])]


def nearest_zone(lat: float, lon: float, zones: tuple[Zone, ...]) -> tuple[Zone, float]:
    """Noktaya merkezi en yakın bölge ve o merkeze kuş uçuşu uzaklık (m)."""
    best = min(zones, key=lambda z: distance_m(lat, lon, z.lat, z.lon))
    return best, distance_m(lat, lon, best.lat, best.lon)


def zone_by_name(name: str, zones: tuple[Zone, ...]) -> Zone | None:
    key = normalize_text(name)
    return next((z for z in zones if normalize_text(z.name) == key), None)

"""Kural tabanlı ön ayrıştırma: koordinat, bölge adı, kategori ve sözlük normalizasyonu.

LLM'e ihtiyaç duymaz. Koordinat ve bölge her zaman buradan gelir (LLM'e sayı kopyalatılmaz).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.engine.geo.zones import find_zones_in_text, normalize_text
from backend.engine.models import Zone

# "39.9374N 32.8483E", "39.9374 N, 32.8483 E", güney/batı işaretleriyle
COORD_RE = re.compile(r"(\d{1,2}\.\d+)\s*([NS])\s*,?\s*(\d{1,3}\.\d+)\s*([EW])", re.IGNORECASE)

# Rapor kelimesi → YOLO sınıfı (heavy = truck|bus, vehicle = herhangi)
VEHICLE_WORDS: dict[str, str] = {
    "kamyon": "truck", "tir": "truck",
    "otomobil": "car", "binek": "car",
    "panelvan": "van", "minibus": "van",
    "otobus": "bus",
}
COLORS = ("mavi", "kirmizi", "sari", "beyaz", "siyah", "yesil", "gri", "turuncu", "kahverengi", "mor")

METERS_PER_DEG = 111_320.0


@dataclass(frozen=True)
class Extracted:
    category: str                     # "coordinate" | "zone" | "general"
    lat: float | None
    lon: float | None
    coord_precision_m: float | None
    zones: tuple[str, ...]
    normalized: str                   # normalize_text(text)


def parse_coordinate(text: str) -> tuple[float, float, float] | None:
    """(lat, lon, hassasiyet_m) — hassasiyet, en az ondalıklı bileşenin yarım biriminin metre karşılığı."""
    m = COORD_RE.search(text)
    if not m:
        return None
    lat, ns, lon, ew = float(m[1]), m[2].upper(), float(m[3]), m[4].upper()
    lat = -lat if ns == "S" else lat
    lon = -lon if ew == "W" else lon
    decimals = min(len(m[1].split(".")[1]), len(m[3].split(".")[1]))
    precision = 0.5 * 10 ** (-decimals) * METERS_PER_DEG
    return lat, lon, round(precision, 1)


def extract(text: str, zones: tuple[Zone, ...]) -> Extracted:
    coord = parse_coordinate(text)
    found = tuple(z.name for z in find_zones_in_text(text, zones))
    category = "coordinate" if coord else ("zone" if found else "general")
    lat, lon, prec = coord if coord else (None, None, None)
    return Extracted(category=category, lat=lat, lon=lon, coord_precision_m=prec,
                     zones=found, normalized=normalize_text(text))


# ---------------------------------------------------------------- sözlük yardımcıları

def vehicle_type_in(normalized: str) -> str | None:
    """Metindeki ilk araç kelimesinin sınıfı. "ağır araç" → heavy, yalnızca "araç" → vehicle."""
    if re.search(r"\bagir\s+(?:bir\s+)?arac", normalized):
        return "heavy"
    best = None
    for word, cls in VEHICLE_WORDS.items():
        m = re.search(rf"\b{word}\w*", normalized)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), cls)
    if best:
        return best[1]
    return "vehicle" if re.search(r"\barac\w*", normalized) else None


def color_in(normalized: str) -> str | None:
    m = re.search(rf"\b({'|'.join(COLORS)})\b", normalized)
    return m[1] if m else None


def count_in(normalized: str) -> int | None:
    """Araç kelimesinden hemen önce yazılan sayı: "5 kamyon", "3 araclik", "1 agir arac"."""
    m = re.search(r"\b(\d+)\s+(?:agir\s+)?(?:kamyon|otomobil|panelvan|otobus|arac)\w*", normalized)
    return int(m[1]) if m else None

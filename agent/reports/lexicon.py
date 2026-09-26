"""Rapor sözlükleri — veriye bakarak genişletilir (RAP-1, VERI-2 bulgusuyla). Görev: RAP-1 · Açık konu: OI-RAP-1"""

# Türkçe kelime → sınıf (ASCII yazımları da ekleyin: "kamyon", "minibus", ...)
TYPE_WORDS: dict[str, str] = {
    "kamyon": "truck",
    "tir": "truck",
    "otobus": "bus",
    "otobüs": "bus",
    "minibus": "van",
    "minibüs": "van",
    "kamyonet": "van",
    "panelvan": "van",
    "otomobil": "car",
    "arac": "car",
    "araç": "car",
}

# Güven verici ama skoru ASLA düşürmeyen ifadeler (README ilke 2)
DE_ESCALATE: list[str] = [
    "tatbikat",
    "dost unsur",
    "rutin",
    "tehdit yok",
]

ESCALATE: list[str] = [
    "silah",
    "hizla",
    "hızla",
    "yaklasiyor",
    "yaklaşıyor",
]

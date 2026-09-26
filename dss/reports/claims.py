"""
Sahibi : Kişi 4
Görev  : Rapor metni -> yapılandırılmış iddia (kategori, tip, sayı, hareket, süre, kimlik, görsel nitelik)

Arayüz (diğer modüller buna güvenir; değiştirmeden önce ekibe haber verin):
    parse_claim(text, zones) -> Claim

Kalıba değil anahtar kelimeye dayanır: veri setindeki 32 kalıbın hepsini kapsar, yeni bir
cümlede de bildiği kadarını çıkarır. Çözemediği kategoriyi None bırakır; karar LLM'indir.
Bu modül hüküm vermez, yalnızca metinde ne iddia edildiğini söyler.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Optional

from dss.schemas import ReportCategory

Motion = Literal["hareketsiz", "usse_yaklasiyor", "uzaklasiyor", "hareketli"]

COORD_RE = re.compile(r"(\d{2}\.(\d+))N\s+(\d{2}\.\d+)E")

# Sıra önemli: ilk eşleşen kategori kazanır
CATEGORY_RULES: list[tuple[ReportCategory, re.Pattern]] = [
    ("gurultu", re.compile(r"hava acik|gorus mesafesi|lojistik konvoyu|telsiz baglantisi|dun gece"
                           r"|ihbar incelendi|tatbikat")),
    ("dost_kimlik", re.compile(r"bize bagli|dost devriye|dost unsur|ikmal araci|kimlik teyidi|teyitlidir")),
    ("olagan_yogunluk", re.compile(r"yogun")),
    ("bolge_olumsuz", re.compile(r"olagandisi bir durum bildirmedi|trafik akisi normal|hareketlilik bulunmuyor"
                                 r"|agir arac hareketi yok")),
    ("hareket_yonu", re.compile(r"uzaklasiyor|transit|ilerliyor|usse dogru|usse gelen")),
    ("hareketsizlik", re.compile(r"hareketsiz|yerinden ayrilmadi|park halinde|bekl(?:emede|eyen|iyor)|durdugu"
                                 r"|duruyor")),
    ("gorulme", re.compile(r"goruldu|gozlendi|ihbar alindi|bulunuyor|bildirildi|\bvar\b")),
]

CLASS_WORDS = [  # (desen, sınıf) — "heavy" = truck veya bus
    (r"agir (?:bir )?arac", "heavy"),
    (r"kamyon(?!et)", "truck"),
    (r"otobus", "bus"),
    (r"panelvan|minibus|kamyonet", "van"),
    (r"otomobil|binek", "car"),
]
COLORS = ["mavi", "kirmizi", "sari", "beyaz", "siyah", "yesil", "gri"]


def norm(s: str) -> str:
    """Küçük harf, Türkçe karakterler ASCII: 'Güney Kapısı' -> 'guney kapisi'."""
    s = unicodedata.normalize("NFKD", s.lower().replace("ı", "i"))
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


@dataclass(frozen=True)
class Claim:
    category: Optional[ReportCategory]
    lat: Optional[float] = None
    lon: Optional[float] = None
    coord_decimals: Optional[int] = None      # 5 hane: belirli bir araç · 4 hane: "civarında"
    zone: Optional[str] = None
    vehicle_class: Optional[str] = None       # car/van/truck/bus/heavy; None = belirtilmemiş
    count: Optional[int] = None
    usual_count: Optional[int] = None         # "genellikle N araç" — olağan yoğunluk iddiası
    motion: Optional[Motion] = None
    duration_min: Optional[int] = None        # "uzun süredir" / "bir saatten uzun" -> 60
    identity: bool = False                    # dost / ikmal / devriye iddiası
    visual: tuple[str, ...] = ()              # renk, yüklü, üzeri örtülü
    past_event: bool = False                  # "dün gece": veri kapsamı dışında
    secondhand: bool = False                  # "sabah devriyesi ... bildirmedi": aktarılan yokluk, bağlamdır


def parse_claim(text: str, zones: list[dict] | None = None) -> Claim:
    t = norm(text)
    category = next((c for c, rx in CATEGORY_RULES if rx.search(t)), None)

    lat = lon = dec = None
    if m := COORD_RE.search(text):
        lat, lon, dec = float(m[1]), float(m[3]), len(m[2])

    zone = next((z["name"] for z in zones or [] if norm(z["name"]) in t), None)
    vclass = next((c for rx, c in CLASS_WORDS if re.search(rx, t)), None)

    usual = None
    if m := re.search(r"(?:genellikle|olagan trafik) (\d+) arac", t):
        usual = int(m[1])
    count = None
    if m := re.search(r"\b(\d+) (?:araclik|kamyon|agir arac|otomobil|panelvan|otobus)", t):
        count = int(m[1])
    elif vclass and category in ("gorulme", "hareketsizlik", "hareket_yonu", "dost_kimlik"):
        count = 1  # tekil ifade: "bir kamyon", "konumundaki otomobil"

    motion = None
    if re.search(r"usse dogru|usse gelen", t):
        motion = "usse_yaklasiyor"
    elif "uzaklasiyor" in t:
        motion = "uzaklasiyor"
    elif re.search(r"transit|ilerliyor", t):
        motion = "hareketli"
    elif category == "hareketsizlik":
        motion = "hareketsiz"

    duration = None
    if m := re.search(r"(\d+) saattir", t):
        duration = int(m[1]) * 60
    elif m := re.search(r"(\d+) dakikadir", t):
        duration = int(m[1])
    elif re.search(r"uzun suredir|bir saatten uzun", t):
        duration = 60

    visual = tuple(c for c in COLORS if re.search(rf"\b{c}\b", t))
    visual += tuple(v for v, rx in [("yuklu", r"\byuklu\b"), ("ortulu", r"ortulu|branda")] if re.search(rx, t))

    return Claim(
        category=category, lat=lat, lon=lon, coord_decimals=dec, zone=zone, vehicle_class=vclass,
        count=count, usual_count=usual, motion=motion,
        duration_min=duration if category != "gurultu" else None,
        identity=category == "dost_kimlik", visual=visual,
        past_event=bool(re.search(r"dun gece|dunden", t)),
        secondhand=bool(re.search(r"devriye\w* .*bildirmedi", t)),
    )

"""
LLM / Agent katmanı veri sözleşmeleri.

İki ana sözleşme var:
  1) EvidencePack  : Kod katmanının ürettiği, LLM'e giden kanıt paketi (görüntü başına bir tane)
  2) Decision      : LLM'in submit_assessment tool'u ile döndürdüğü karar

Kimlik kuralları (LLM gerekçelerinde bunlara atıf yapar, validator varlıklarını kontrol eder):
  D1, D2 ...        tespitler (görüntü içinde sıralı)
  T0122 ...         track_id (tracks.csv'deki gibi)
  R001 ... R137     raporlar (field_reports.json sırası, 1'den başlar)
  F1, F2 ...        sert bayraklar (kodun ürettiği)
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"

Level = Literal["DUSUK", "ORTA", "YUKSEK", "KRITIK"]
LEVEL_ORDER = ["DUSUK", "ORTA", "YUKSEK", "KRITIK"]
VehicleClass = Literal["car", "van", "truck", "bus"]
Source = Literal["official", "third_party"]


# ═══════════════════════════ 1) KANIT PAKETİ ═══════════════════════════

class ImageInfo(BaseModel):
    image_id: str
    capture_time: str                      # "HH:MM"
    width_px: int
    height_px: int
    zone: str                              # karenin en yakın olduğu bölge
    center_lat: float
    center_lon: float
    dist_to_base_m: int                    # kare merkezinin üsse uzaklığı
    footprint_m: tuple[int, int]           # (genişlik, yükseklik) metre


class DetectionEv(BaseModel):
    det_id: str                            # "D1"
    label: VehicleClass
    conf: float
    lat: float
    lon: float
    dist_to_base_m: int
    track_id: Optional[str] = None         # eşleşme yoksa None → park halinde olabilir
    match_dist_m: Optional[float] = None


class StopEv(BaseModel):
    start: str
    end: str
    minutes: int
    dist_to_base_m: int


class MotionEv(BaseModel):
    """Bir track'in 2 saatlik özeti. Tüm sayılar koddan gelir."""
    track_id: str
    det_id: Optional[str] = None           # görüntüdeki tespitle eşleştiyse
    window: str                            # "11:25-13:25"
    dist_start_m: int
    dist_min_m: int
    dist_now_m: int
    approach_rate_30m_mps: float           # + ise son 30 dk'da üsse yaklaşıyor
    avg_speed_mps: float                   # hareketli segmentlerin ortalaması
    speed_last_30m_mps: float
    heading_deg: int                       # 0=kuzey, saat yönü
    heading_cardinal: str                  # "KD", "G" ...
    toward_base_cos: float                 # 1 üsse doğru, -1 üsten uzağa
    path_len_m: int
    eta_min: Optional[float] = None        # mevcut yaklaşma hızıyla üsse varış
    stops: list[StopEv] = []
    pattern: Literal["yaklasiyor", "uzaklasiyor", "duraklayip_yaklasiyor",
                     "dolaniyor", "sabit", "teget_geciyor"]


class UnmatchedTrack(BaseModel):
    track_id: str
    reason: Literal["kare_disinda", "karede_ama_tespit_yok"]
    dist_to_frame_m: int


class NearTrack(BaseModel):
    track_id: str
    dist_m: int


class NearDetection(BaseModel):
    det_id: str
    label: VehicleClass
    dist_m: int
    has_track: bool


class ReportChecks(BaseModel):
    """Kodun hesapladığı objektif kontroller. LLM bunları iddiayla karşılaştırır."""
    tracks_near_at_report_time: list[NearTrack]      # rapor saatinde ±5 dk, 150 m içi
    detections_near: list[NearDetection]             # çekim anında 150 m içi tespitler
    stationary_tracks_near: list[str]                # rapor saatine kadar ≥30 dk duran track'ler
    label_counts_near: dict[str, int]                # {"truck": 1, "car": 2}


class ReportEv(BaseModel):
    report_id: str                         # "R001"
    time: str
    source: Source
    text: str                              # HAM METİN — güvenilmeyen veri
    scope: Literal["koordinat", "bolge", "genel"]
    lat: Optional[float] = None
    lon: Optional[float] = None
    minutes_before_capture: int
    dist_to_frame_center_m: Optional[int] = None
    checks: Optional[ReportChecks] = None  # yalnızca koordinatlı raporlarda


class HardFlag(BaseModel):
    """Kural tabanlı sert bayrak. Kararın ALT SINIRINI belirler."""
    flag_id: str                           # "F1"
    code: Literal["YAKIN_YAKLASMA", "YAKIN_VARIS", "AGIR_ARAC_YAKIN",
                  "UZUN_BEKLEME_YAKIN", "IZSIZ_AGIR_ARAC"]
    description: str
    evidence: list[str]
    min_level: Level


class ZoneSummary(BaseModel):
    """Bölge geneli raporları doğrulamak için: bu görüntüde sınıf bazında sayım."""
    zone: str
    detected_counts: dict[str, int]
    heavy_vehicle_present: bool            # truck veya bus var mı


class EvidencePack(BaseModel):
    schema_version: str = SCHEMA_VERSION
    image: ImageInfo
    detections: list[DetectionEv]
    motions: list[MotionEv]
    unmatched_tracks: list[UnmatchedTrack]
    zone_summary: ZoneSummary
    reports: list[ReportEv]                # koordinatlı + bölge raporları (karar verilecek)
    context_reports: list[ReportEv]        # konumsuz genel raporlar (yalnızca bağlam)
    hard_flags: list[HardFlag]
    rule_floor: Level                      # hard_flags'in en yüksek min_level'i
    notes: list[str] = []


# ═══════════════════════════ 2) KARAR ═══════════════════════════

ReportCategory = Literal[
    "gorulme",           # tip/sayı/konum iddiası
    "hareketsizlik",     # uzun süredir duruyor / park
    "hareket_yonu",      # üsse doğru / uzaklaşıyor / transit
    "dost_kimlik",       # bize bağlı unsur, dost devriye, planlı ikmal
    "bolge_olumsuz",     # bölgede ağır araç yok / olağandışı durum yok
    "olagan_yogunluk",   # olağan trafik N araç
    "gorsel_nitelik",    # renk, yüklü, üzeri örtülü
    "gurultu",           # hava, konvoy, telsiz, dün gece ihbarı, genel tatbikat
]
ReportStatus = Literal["DOGRULANDI", "KISMEN_DOGRULANDI", "CELISIYOR",
                       "DOGRULANAMADI", "ILGISIZ"]


class ReportVerdict(BaseModel):
    report_id: str
    category: ReportCategory
    claim: str = Field(description="Raporun iddiası, tek cümle, kendi kelimelerinle")
    status: ReportStatus
    reason: str = Field(description="Hangi kanıtla neden bu sonuca varıldı")
    evidence: list[str] = Field(description="Atıf yapılan kimlikler: D1, T0122, F1 ...")
    risk_effect: Literal["arttirir", "etkisiz", "azaltir"]


class VehicleAssessment(BaseModel):
    det_id: Optional[str] = None
    track_id: Optional[str] = None
    level: Level
    observations: list[str] = Field(description="Koddan gelen sayılarla, en fazla 3 madde")
    evidence: list[str]


class Decision(BaseModel):
    """submit_assessment tool'unun parametre şeması."""
    image_id: str
    attention_required: bool
    attention_level: Level
    vehicles: list[VehicleAssessment]
    report_verdicts: list[ReportVerdict]
    key_findings: list[str] = Field(max_length=5)
    summary: str = Field(description="Operatör için 3-5 cümlelik brief, Türkçe")
    recommended_action: str
    deviation_from_rules: Optional[str] = Field(
        default=None, description="attention_level rule_floor'dan YÜKSEKSE gerekçe")
    confidence: Literal["dusuk", "orta", "yuksek"]

"""Motorun veri tipleri ve enum'ları.

Zaman içeride gün başından itibaren dakika (int) olarak tutulur; dışarıya "HH:MM" verilir.
Koordinatlar (lat, lon) WGS84 derecesidir.
Türetilmiş tipler (eşleşme, kinematik, iddia, dossier...) ait oldukları step'te buraya eklenir.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

LatLon = tuple[float, float]


# ---------------------------------------------------------------- zaman

def parse_hhmm(value: str) -> int:
    """"13:25" -> 805"""
    hours, minutes = value.strip().split(":")
    h, m = int(hours), int(minutes)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"Geçersiz saat: {value!r}")
    return h * 60 + m


def fmt_hhmm(minutes: int) -> str:
    """805 -> "13:25\""""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ---------------------------------------------------------------- enum'lar

class Source(str, Enum):
    OFFICIAL = "official"
    THIRD_PARTY = "third_party"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClaimStatus(str, Enum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class ClaimType(str, Enum):
    COUNT = "count"
    STATIONARY = "stationary"
    MOTION = "motion"
    IDENTITY = "identity"
    DENSITY = "density"
    ZONE_STATUS = "zone_status"
    NOISE = "noise"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------- temel tipler

class Serializable:
    def to_dict(self) -> dict:
        return _plain(asdict(self))


def _plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


@dataclass(frozen=True)
class Base(Serializable):
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Zone(Serializable):
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Corners(Serializable):
    top_left: LatLon
    top_right: LatLon
    bottom_left: LatLon
    bottom_right: LatLon


@dataclass(frozen=True)
class ImageMeta(Serializable):
    id: str
    width_px: int
    height_px: int
    capture_min: int
    corners: Corners
    file: Path
    annotated_file: Path | None = None

    @property
    def capture_time(self) -> str:
        return fmt_hhmm(self.capture_min)

    @property
    def lat_bounds(self) -> tuple[float, float]:
        lats = (self.corners.top_left[0], self.corners.bottom_left[0])
        return min(lats), max(lats)

    @property
    def lon_bounds(self) -> tuple[float, float]:
        lons = (self.corners.top_left[1], self.corners.top_right[1])
        return min(lons), max(lons)

    @property
    def center(self) -> LatLon:
        (lat0, lat1), (lon0, lon1) = self.lat_bounds, self.lon_bounds
        return (lat0 + lat1) / 2, (lon0 + lon1) / 2


@dataclass(frozen=True)
class AltLabel(Serializable):
    label: str
    confidence: float


@dataclass(frozen=True)
class RawPrediction(Serializable):
    """Modelin eşik altı (ham) tahmini — stage2_final.csv. Yalnızca kaçırılmış araç adayı aramak için."""
    label: str
    confidence: float
    bbox_xywh: tuple[float, float, float, float]


@dataclass(frozen=True)
class Detection(Serializable):
    id: str
    image_id: str
    label: str
    confidence: float
    bbox_xywh: tuple[float, float, float, float]
    center_px: tuple[float, float]
    lat: float
    lon: float
    alt_labels: tuple[AltLabel, ...] = ()


@dataclass(frozen=True)
class TrackPoint(Serializable):
    t: int
    lat: float
    lon: float

    @property
    def time(self) -> str:
        return fmt_hhmm(self.t)


@dataclass(frozen=True)
class Track(Serializable):
    id: str
    points: tuple[TrackPoint, ...]
    image_id: str | None = None   # çekim saati track'in son noktasına eşit olan görüntü

    @property
    def start_min(self) -> int:
        return self.points[0].t

    @property
    def end_min(self) -> int:
        return self.points[-1].t

    @property
    def last(self) -> TrackPoint:
        return self.points[-1]

    def position_at(self, t: int) -> TrackPoint | None:
        """t anındaki konum. Izgara dışındaki anlarda doğrusal enterpolasyon; kayıt aralığı dışında None."""
        if t < self.start_min or t > self.end_min:
            return None
        for a, b in zip(self.points, self.points[1:]):
            if a.t == t:
                return a
            if a.t < t < b.t:
                w = (t - a.t) / (b.t - a.t)
                return TrackPoint(t=t, lat=a.lat + w * (b.lat - a.lat), lon=a.lon + w * (b.lon - a.lon))
        return self.points[-1]

    def points_until(self, t: int) -> tuple[TrackPoint, ...]:
        """t anına kadarki noktalar; t ızgara dışındaysa sona enterpole nokta eklenir."""
        pts = tuple(p for p in self.points if p.t <= t)
        if pts and pts[-1].t != t:
            end = self.position_at(t)
            if end is not None:
                pts = pts + (end,)
        return pts


@dataclass(frozen=True)
class Report(Serializable):
    id: str            # R001.. (dosyadaki sıraya göre, kararlı)
    index: int         # dosyadaki 0 tabanlı sıra
    t: int
    source: Source
    text: str

    @property
    def time(self) -> str:
        return fmt_hhmm(self.t)


@dataclass(frozen=True)
class Dataset:
    """Loader'ların ham çıktısı; repository bunu indeksler."""
    base: Base
    zones: tuple[Zone, ...]
    images: tuple[ImageMeta, ...]
    detections: tuple[Detection, ...]
    tracks: tuple[Track, ...]
    reports: tuple[Report, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------- Step 3: eşleştirme

@dataclass(frozen=True)
class Match(Serializable):
    detection_id: str
    track_id: str
    dist_m: float
    alternatives: tuple[str, ...] = ()   # kapı içinde kalan diğer aday track'ler (belirsizlik göstergesi)


@dataclass(frozen=True)
class UnmatchedTrack(Serializable):
    track_id: str
    in_frame: bool                  # son nokta görüntü içinde → olası kaçırılmış tespit
    dist_to_footprint_m: float


@dataclass(frozen=True)
class ImageMatch(Serializable):
    image_id: str
    matches: tuple[Match, ...]
    unmatched_detections: tuple[str, ...]   # track'i olmayan tespitler (park halinde / yanlış pozitif)
    unmatched_tracks: tuple[UnmatchedTrack, ...]

    def track_for(self, detection_id: str) -> str | None:
        return next((m.track_id for m in self.matches if m.detection_id == detection_id), None)

    def detection_for(self, track_id: str) -> str | None:
        return next((m.detection_id for m in self.matches if m.track_id == track_id), None)


# ---------------------------------------------------------------- Step 3: kinematik

@dataclass(frozen=True)
class Segment(Serializable):
    kind: str                # "stop" | "move"
    start: str               # HH:MM
    end: str
    duration_min: int
    distance_m: float        # stop: 0; move: kat edilen yol
    radial_change_m: float   # üsse uzaklık değişimi (negatif = yaklaştı)


@dataclass(frozen=True)
class Kinematics(Serializable):
    track_id: str
    at: str                            # hesaplamanın yapıldığı an (HH:MM)
    lat: float
    lon: float
    state: str                         # "stationary" | "moving" (son adıma göre)
    motion: str                        # "approaching" | "receding" | "lateral" | "stationary" (radyal pencereye göre)
    dist_to_base_m: float
    dist_to_base_window_ago_m: float | None
    dist_to_base_start_m: float
    min_dist_to_base_m: float
    radial_change_window_m: float | None   # radial_window_min içinde üsse uzaklık değişimi (negatif = yaklaştı)
    radial_speed_mps: float | None         # aynı pencerede ortalama radyal hız
    speed_mps: float                       # speed_window_min içinde kat edilen yol / süre
    displacement_speed_mps: float          # aynı pencerede net yer değiştirme / süre
    eta_min: float | None                  # yaklaşıyor ve duruşu kısaysa: mevcut uzaklık / |radyal hız|
    stationary_min: int                    # mevcut duruşun süresi
    total_stationary_min: int
    heading_deg: float | None              # son hareketin yönü
    heading_to_base_diff_deg: float | None # son hareket yönü ile üsse yön arasındaki fark
    moves: int
    approach_moves: int
    recede_moves: int
    consistent_approach: bool              # tüm hareketler üsse yaklaştırdı (en az N hareket)
    path_length_m: float
    net_displacement_m: float
    tortuosity: float | None               # yol / net yer değiştirme (dolaşma göstergesi)
    observed_min: int                      # hesaba giren kayıt süresi
    segments: tuple[Segment, ...] = ()


# ---------------------------------------------------------------- Step 5: rapor iddiaları ve bağlantıları

VEHICLE_TYPES = ("car", "van", "truck", "bus", "heavy", "vehicle")   # heavy = truck|bus, vehicle = herhangi
MOTIONS = ("approaching_base", "leaving_area", "transit", "moving", "normal_activity", "stationary")
ZONE_STATUSES = ("normal", "no_heavy", "unverified_tip", "comms_lost")
CARGO = ("unknown", "loaded", "covered")


@dataclass(frozen=True)
class Claim(Serializable):
    """Bir raporun yapısal hali. Koordinat ve bölge her zaman kural tabanlı çıkarılır; geri kalanı parser'dan."""
    report_id: str
    category: str                          # "coordinate" | "zone" | "general"
    claim_types: tuple[ClaimType, ...]     # birincil önce
    lat: float | None = None
    lon: float | None = None
    coord_precision_m: float | None = None # koordinatın ondalık hassasiyeti (4 hane ≈ ±6 m)
    zone: str | None = None
    vehicle_type: str | None = None        # VEHICLE_TYPES
    count: int | None = None               # açıkça yazılan sayı
    motion: str | None = None              # MOTIONS
    stationary_min: int | None = None      # "bir saatten uzun" → 60; "uzun süredir" → None (süre belirtilmemiş)
    friendly: bool = False                 # dost / planlı ikmal / kimlik teyitli iddiası
    blanket_friendly: bool = False         # konumsuz genel dost iddiası ("gün içinde dost unsurlar bulunacak")
    color: str | None = None
    cargo: str | None = None               # CARGO
    normal_count: int | None = None        # yoğunluk iddiasındaki "olağan" sayı
    zone_status: str | None = None         # ZONE_STATUSES
    hedged: bool = False                   # rapor kendi kesinliğini düşürüyor ("ihbar", "bir kaynak", "doğrulanmamış")
    parser: str = "rules"                  # "llm" | "rules"
    parse_notes: tuple[str, ...] = ()      # LLM ↔ kural uyuşmazlıkları vb.


@dataclass(frozen=True)
class ImageLink(Serializable):
    image_id: str
    dist_to_footprint_m: float
    minutes_before_capture: int


@dataclass(frozen=True)
class TrackLink(Serializable):
    track_id: str
    dist_m: float                  # rapor saatinde track konumu ↔ rapor koordinatı
    image_id: str | None


@dataclass(frozen=True)
class DetectionLink(Serializable):
    detection_id: str
    image_id: str
    label: str
    dist_m: float                  # çekim anındaki tespit ↔ rapor koordinatı


@dataclass(frozen=True)
class ReportLinks(Serializable):
    report_id: str
    zone: str | None                       # metindeki bölge ya da koordinata en yakın bölge
    images: tuple[ImageLink, ...] = ()
    tracks: tuple[TrackLink, ...] = ()     # rapor saatinde yakındaki track'ler (mesafeye göre sıralı)
    detections: tuple[DetectionLink, ...] = ()  # bağlı görüntülerde koordinata yakın tespitler (park halindekiler dahil)
    nearest_track_m: float | None = None   # rapor saatinde en yakın track (yarıçap dışında olsa bile)
    zone_tracks: tuple[str, ...] = ()      # bölge raporu: rapor saatinde o bölgede kaydı olan track'ler


# ---------------------------------------------------------------- Step 6: doğrulama, risk, dossier

@dataclass(frozen=True)
class Subject(Serializable):
    """Raporun anlattığı olası araç."""
    kind: str                      # "tracked" (rapor saatinde yakında track var) | "parked" (track'siz tespit)
    detection_id: str | None
    track_id: str | None
    label: str | None              # eşleşen tespitin etiketi (tespitsiz track'te None)
    dist_m: float                  # tracked: rapor saatindeki konum; parked: çekimdeki tespit ↔ rapor koordinatı


@dataclass(frozen=True)
class ClaimCheck(Serializable):
    report_id: str
    time: str
    source: str
    claim_type: ClaimType
    status: ClaimStatus
    reason: str                    # Türkçe, sayılarla gerekçe
    subjects: tuple[Subject, ...] = ()
    observed: dict = field(default_factory=dict)   # ör. {"claimed": 5, "observed": 1}
    evidence: tuple[str, ...] = () # "det:..", "track:..", "report:..", "image:.."


@dataclass(frozen=True)
class RiskFactor(Serializable):
    name: str
    weight: int
    detail: str


@dataclass(frozen=True)
class BaselineRisk(Serializable):
    score: int
    level: RiskLevel
    factors: tuple[RiskFactor, ...]


@dataclass(frozen=True)
class VehicleEvidence(Serializable):
    vehicle_id: str                        # tespit id'si; tespitsiz track için "track:<id>"
    label: str | None
    confidence: float | None
    alt_labels: tuple[AltLabel, ...]
    bbox_xywh: tuple[float, float, float, float] | None
    lat: float
    lon: float
    dist_to_base_m: float
    zone: str
    track_id: str | None
    match_dist_m: float | None
    kinematics: Kinematics | None
    claims: tuple[ClaimCheck, ...]
    flags: tuple[str, ...]                 # parked, low_confidence, possible_missed_detection, ambiguous_match, coordinated
    baseline_risk: BaselineRisk
    candidates: tuple[RawPrediction, ...] = ()   # tespitsiz track: yakındaki eşik altı ham tahminler (güvene göre)


@dataclass(frozen=True)
class Anomaly(Serializable):
    type: str
    detail: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportSummary(Serializable):
    report_id: str
    time: str
    source: str
    text: str
    claim_types: tuple[ClaimType, ...]
    checks: tuple[ClaimCheck, ...] = ()


@dataclass(frozen=True)
class ImageDossier(Serializable):
    image_id: str
    capture_time: str
    zone: str
    center: LatLon
    dist_to_base_m: float
    footprint_m: tuple[float, float]
    vehicles: tuple[VehicleEvidence, ...]
    reports: tuple[ReportSummary, ...]           # bu görüntüye bağlanan koordinatlı raporlar
    context_reports: tuple[ReportSummary, ...]   # bölge raporları ve konumsuz dost/gürültü duyuruları
    anomalies: tuple[Anomaly, ...]
    max_risk: RiskLevel
    risk_counts: dict
    global_context: dict = field(default_factory=dict)   # çekim anında tüm bölgelerdeki genel tablo

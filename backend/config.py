"""Tek yapılandırma noktası: yollar, LLM ayarları ve tüm eşikler.

Kodun geri kalanında sabit sayı yazılmaz; eşikler buradan okunur.
Değerlerin gerekçeleri için CASE.md'ye bakın.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Paths:
    root: Path = ROOT_DIR
    stage2: Path = ROOT_DIR / "stage2"
    images: Path = ROOT_DIR / "stage2" / "images"
    image_meta: Path = ROOT_DIR / "stage2" / "image_meta.json"
    zones: Path = ROOT_DIR / "stage2" / "zones.json"
    tracks: Path = ROOT_DIR / "stage2" / "tracks.csv"
    reports: Path = ROOT_DIR / "stage2" / "field_reports.json"
    detections_dir: Path = ROOT_DIR / "detections_output" / "detections_output"
    detections: Path = ROOT_DIR / "detections_output" / "detections_output" / "detections.json"
    low_conf_predictions: Path = ROOT_DIR / "detections_output" / "detections_output" / "stage2_final.csv"
    annotated_images: Path = ROOT_DIR / "detections_output" / "detections_output" / "plots"
    prompts: Path = ROOT_DIR / "backend" / "prompts"
    outputs: Path = ROOT_DIR / "outputs"
    llm_cache: Path = ROOT_DIR / "outputs" / "cache" / "llm"
    claims: Path = ROOT_DIR / "outputs" / "claims.json"
    dossiers: Path = ROOT_DIR / "outputs" / "dossiers"
    assessments: Path = ROOT_DIR / "outputs" / "assessments"
    logs: Path = ROOT_DIR / "outputs" / "logs"


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = os.getenv("LLM_BASE_URL", "")
    model: str = os.getenv("LLM_MODEL", "glm-5.3-flash")
    api_key: str = os.getenv("LLM_API_KEY", "")
    max_concurrency: int = 4          # gateway limiti: aynı anda 4 istek
    requests_per_minute: int = 60     # gateway limiti
    max_retries: int = 5
    timeout_s: float = 120.0
    max_tokens: int = 8000            # düşünme de bu bütçeden yer; düşük tutulmamalı
    budget_stop_usd: float = 13.0     # 15 USD'lik bütçenin bu noktasında yeni istek atılmaz

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.base_url)


@dataclass(frozen=True)
class MatchConfig:
    gate_m: float = 5.0               # tespit↔track birebir eşleşme kapısı (veride 3–15 m arası fark yok)
    min_confidence: float = 0.10      # detections.json zaten bu eşikle geliyor
    low_confidence: float = 0.30      # altı "düşük güvenli" işaretlenir
    missed_candidate_radius_m: float = 3.0  # tespitsiz track'in son noktasına bu kadar yakın eşik altı tahminler aday
    ambiguity_margin_m: float = 1.0   # seçilen eşleşmeden bu kadar yakın başka track varsa "belirsiz" (alternatif) sayılır


@dataclass(frozen=True)
class KinematicsConfig:
    # Veri: bekleme sırasında ardışık noktalar arası titreme < 20 m; gerçek hareket adımları ≥ 76 m (çoğu 1–3 km).
    step_min: int = 5                 # track örnekleme adımı
    move_step_m: float = 60.0         # tek adımda bunun üstü "hareket", altı "bekleme"
    stationary_radius_m: float = 30.0 # bekleme noktalarının duruş merkezine en fazla uzaklığı
    speed_window_min: int = 30        # hız penceresi (PDF örneği: "son yarım saatte hızı")
    radial_window_min: int = 60       # üsse uzaklık değişimi penceresi (PDF örneği: 12:25 → 13:25)
    approach_net_m: float = 300.0     # pencerede üsse uzaklık bu kadar azaldıysa "yaklaşıyor", arttıysa "uzaklaşıyor"
    heading_to_base_deg: float = 45.0 # son hareket yönü üsse bu açıdan yakınsa "üsse yöneliyor"
    consistent_approach_min_moves: int = 3  # en az bu kadar hareketin hepsi üsse yaklaştırdıysa "tutarlı yaklaşma"
    # Üssün etrafında dönme: ≥N ardışık nokta, üsse uzaklık ±band içinde sabit, yakın yarıçap, geniş açı taraması
    # (veri: T0034 kamyonu 14:45–15:05 tam 527 m'de 5 farklı bölgeden geçiyor; T0172/T0158/T0198 de benzer)
    circle_min_points: int = 3
    circle_band_m: float = 30.0
    circle_max_radius_m: float = 1500.0
    circle_min_sweep_deg: float = 120.0
    close_pass_m: float = 1000.0      # kayıt içinde üsse bundan yakın geçiş (dönmeden bağımsız)


@dataclass(frozen=True)
class ReportConfig:
    link_radius_m: float = 150.0      # rapor koordinatı ↔ görüntü ayak izi (veride en fazla 133 m)
    track_link_radius_m: float = 150.0  # görüntüde koordinata bu yarıçaptaki araçlar bağlanır (yoğunluk sayımı)
    track_close_m: float = 60.0       # sayım iddiaları: görüntüde koordinata bu yarıçaptaki araçlar sayılır
    window_min: int = 120             # rapor, çekimden en fazla bu kadar önce olabilir (track uzunluğu)
    stationary_claim_default_min: int = 60
    long_stationary_min: int = 30     # süresiz "uzun süredir hareketsiz" iddiası için asgari duruş
    subject_tolerance_min_m: float = 3.0   # rapor koordinatı ↔ görüntüdeki araç (5 ondalık: 31/35 ≤3 m)
    behavior_window_min: int = 30     # iddia, aracın rapordan önceki bu kadar dakikadaki davranışıyla değerlendirilir
    after_approach_m: float = 1000.0  # güven verici iddiadan SONRA üsse bu kadar yaklaşan araç → iddia yanıltıcı işaretlenir
    zone_lookback_min: int = 15       # bölge raporu: son bu kadar dakikada bölgede bulunan araçlar da sayılır
    parser_mode: str = "llm"          # "llm": LLM + kural çapraz kontrolü (LLM yoksa kurallar) | "rules": yalnızca kurallar


@dataclass(frozen=True)
class RiskConfig:
    # Seviye sınırları (0–100 skor)
    critical_at: int = 70
    high_at: int = 50
    medium_at: int = 25
    # Mesafe bantları (m)
    near_base_m: float = 2000.0
    mid_base_m: float = 3500.0
    # Ağırlıklar — Step 6'da elle inceleme ile kalibre edilir
    weights: dict = field(default_factory=lambda: {
        "near_base": 20,
        "mid_base": 10,
        "approaching": 10,
        "fast_approach": 10,
        "short_eta": 15,
        "consistent_approach": 20,
        "heavy_vehicle": 15,
        "long_stationary_near_base": 10,
        "loitering": 10,
        "group": 10,
        "circling_base": 35,
        "close_pass": 10,
        # Yalnızca riski DÜŞÜRMEYE yönelik iddialar (dost / "olağan" / "uzaklaşıyor") risk etkiler:
        # gözlemle çelişirse ya da üsse yaklaşan araca iliştirilmişse şüphe sinyalidir. Kimlik teyit edilemediği
        # için hiçbir dost iddiası riski DÜŞÜRMEZ (eski "verified_friendly_claim −15" kaldırıldı).
        "reassuring_claim": 10,
        "receding": -10,
        "low_confidence": -10,
    })
    short_eta_min: float = 15.0
    fast_approach_m: float = 2000.0   # radyal pencerede bu kadar yaklaşma "hızlı yaklaşma"
    long_stationary_min: int = 60
    loiter_tortuosity: float = 3.0
    loiter_min_moves: int = 4
    group_radius_m: float = 100.0     # aynı görüntüde bu yarıçapta ≥ group_min ağır araç → grup
    group_min: int = 3


@dataclass(frozen=True)
class AgentConfig:
    max_iterations: int = 8           # sonsuz döngüye karşı üst sınır (son iterasyon her zaman cevaba ayrılır)
    max_tool_calls: int = 6           # görüntü başına tool çağrısı üst sınırı
    reasoning_effort: str = "high"    # agent kararı
    parser_reasoning_effort: str = "low"  # rapor ayrıştırma
    vision_reasoning_effort: str = "low"
    # Tool sınırları (agent'ın aşırı geniş sorgularla token/bütçe harcamasını engeller)
    tool_max_items: int = 25
    area_max_radius_m: float = 2000.0
    area_max_window_min: int = 180
    co_move_max_tracks: int = 6
    co_move_radius_m: float = 150.0   # ortak adımlarda en fazla bu kadar ayrılan araçlar "birlikte"
    co_move_min_sync: int = 2         # hep yakın + en az bu kadar aynı 5 dk'da hareket → "birlikte hareket" (konvoy)
    converge_min_sync: int = 4        # ayrı yerlerden en az bu kadar aynı anda aynı yöne hareket → "buluştular"
                                      # (veri: rastgele çiftlerde ≥2 %43, ≥3 %19–24, ≥4 %2–5 tesadüfen görülür;
                                      #  580 çiftte ≥4 → ~29 tesadüfi eşleşme: tek başına sinyal değil)


@dataclass(frozen=True)
class Settings:
    paths: Paths = field(default_factory=Paths)
    llm: LLMConfig = field(default_factory=LLMConfig)
    match: MatchConfig = field(default_factory=MatchConfig)
    kinematics: KinematicsConfig = field(default_factory=KinematicsConfig)
    reports: ReportConfig = field(default_factory=ReportConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


settings = Settings()

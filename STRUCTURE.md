# Proje Yapısı

Reponun **klasör/dosya haritası**. Her dosyanın yanında onu yazan step yazıyor ([STEPS.md](STEPS.md)).
`[0]` Step 0'da hazırlanmış ortak altyapı demek; bu dosyalar sadece ekip kararıyla değişir.

## 1. Ağaç

```
dss/
├── README.md  STEPS.md  STRUCTURE.md  CONTRIBUTING.md  OPEN_ISSUES.md  PROGRESS.md
├── requirements.txt  pyproject.toml  .env.example  .gitignore  .gitattributes
├── app.py                      [0]  Streamlit girişi — sadece sekmeleri bağlar
├── cli.py                      UI-5 komut satırı (demo yedeği)
│
├── agent/                      ── ÇEKİRDEK ─────────────────────────────────────
│   ├── schemas/                [0]  Sözleşmeler — alan başına bir dosya
│   │   ├── common.py                VehicleClass, RiskLevel, LatLon, hhmm_to_min
│   │   ├── inputs.py                ImageMeta, ZonesFile, TrackPoint, FieldReport
│   │   ├── detection.py  geo.py  tracks.py  reports.py  risk.py  pipeline.py
│   │   └── __init__.py              hepsini dışa aktarır: from agent.schemas import X
│   ├── config/                 Ayarlar — alan başına bir dosya
│   │   ├── paths.py            [0]  veri/model/cache yolları
│   │   ├── detection.py        DET-4
│   │   ├── tracks.py           TRK-1 (eşleştirme bölümü) · TRK-2 (hareket bölümü)
│   │   ├── risk.py             RSK-1..3 (kendi bölümleri) · SON-2 (seviyeler)
│   │   └── llm.py              LLM-1
│   ├── loaders.py              [0]  veri dosyası okuyucular
│   ├── fakes.py                [0]  sahte veri — başkasını beklemeden geliştirme/test
│   │
│   ├── detection/              AKIŞ 01
│   │   ├── detector.py         DET-2
│   │   └── cache.py            DET-3
│   ├── geo/                    AKIŞ 02
│   │   ├── spatial.py          [0]  distance_m, bearing_deg, nearest_zone
│   │   ├── projection.py       GEO-1  piksel → lat/lon
│   │   ├── checks.py           GEO-1  check_north_up
│   │   └── locate.py           GEO-2
│   ├── tracks/                 AKIŞ 03
│   │   ├── timeline.py         [0]  series, positions_at
│   │   ├── matching.py         TRK-1
│   │   └── motion.py           TRK-2
│   ├── reports/                AKIŞ 04a
│   │   ├── lexicon.py          RAP-1
│   │   ├── extraction.py       RAP-2
│   │   ├── verification.py     RAP-3
│   │   └── llm_extraction.py   LLM-3  (extraction'a fallback olarak takılır)
│   ├── risk/                   AKIŞ 04b
│   │   ├── registry.py         [0]  @rule, RuleContext
│   │   ├── scoring.py          [0]  motor: kuralları çalıştır, topla, seviye
│   │   └── rules/              her .py otomatik yüklenir
│   │       ├── proximity.py    RSK-1
│   │       ├── motion.py       RSK-2
│   │       └── reports.py      RSK-3
│   ├── llm/
│   │   ├── client.py           LLM-1
│   │   ├── brief.py            LLM-2
│   │   └── prompts/            brief_system.md (LLM-2) · report_extraction.md (LLM-3) · chat_system.md (LLM-5)
│   ├── chat/
│   │   ├── tools/              her .py otomatik yüklenir
│   │   │   ├── registry.py     [0]  @tool, schemas(), dispatch()
│   │   │   ├── assessment.py   LLM-4
│   │   │   └── data.py         LLM-4
│   │   └── agent.py            LLM-5
│   └── pipeline.py             PIP-1 (run_events, run) · PIP-2 (scan_all)
│
├── ui/                         Her sekme ayrı dosya
│   ├── map_view.py             UI-1
│   ├── tab_evaluate.py         UI-2
│   ├── tab_status.py           UI-3
│   └── tab_chat.py             UI-4
│
├── scripts/
│   ├── check_data.py           VERI-1
│   ├── build_detection_cache.py  DET-3
│   └── scan_all.py             PIP-2
│
├── tests/                      Her step'in kendi test dosyası
│   ├── conftest.py             [0]
│   ├── test_foundation.py  test_risk_engine.py  test_chat_tools.py   [0]
│   ├── test_detection.py (DET-2)  test_projection.py (GEO-1)  test_locate.py (GEO-2)
│   ├── test_matching.py (TRK-1)  test_motion.py (TRK-2)
│   ├── test_extraction.py (RAP-2)  test_verification.py (RAP-3)
│   ├── test_rule_proximity.py (RSK-1)  test_rule_motion.py (RSK-2)  test_rule_reports.py (RSK-3)
│   ├── test_brief.py (LLM-2)
│   └── test_reference_img_000860.py (SON-1)
│
├── data/                       ── VERİ ALANI ───────────────────────────────────
│   ├── README.md               beklenen paket yapısı
│   ├── raw/                    organizasyonun paketi + gorev_tanimi.pdf — commit'li, dokunulmaz
│   └── samples/                sunumdaki örnekler — testler kullanır
├── exploration/                ── İNCELEME ALANI ───────────────────────────────
│   ├── notebooks/              NN_K<no>_konu.ipynb — kişiye özel
│   └── findings/               YYYYMMDD_K<no>_konu.md — bulgular (VERI-1, VERI-2, DET-4, SON-2)
├── kaggle/                     DET-1 — Aşama 1 notebook'ları
├── models/                     (git dışı) best.pt
├── cache/                      (git dışı) tespit + LLM cache
├── docs/presentation/          SUN-1..3
└── .github/pull_request_template.md
```

## 2. Bağımlılık yönü

```
schemas  ◄──  config, loaders, fakes
   ▲
geo.spatial, tracks.timeline         (Step 0 yardımcıları)
   ▲
detection · geo · tracks · reports · risk · llm     ← birbirini import ETMEZ
   ▲
pipeline                                             ← hepsini sırayla çağırır
   ▲
chat.tools  ·  ui  ·  cli                            ← sadece pipeline / loaders / schemas
```

- Alan modülleri (`detection`, `geo`, `tracks`, `reports`, `risk`, `llm`) birbirini import etmez. Sadece
  `schemas`, `config` ve Step 0 yardımcılarını kullanırlar. Bu yüzden her step bağımsız yazılıp test edilebilir.
  (Bir istisna var: `reports/llm_extraction.py` → `llm/client.py`. İkisi de LLM hattında.)
- `agent/` hiçbir zaman `ui/`, `exploration/` veya `tests/` içinden import yapmaz.

## 3. Genişletme noktaları

| Ne eklenecek | Nereye | Başka dosyaya dokunmak gerekir mi? |
|---|---|---|
| Risk kuralı | `agent/risk/rules/<dosya>.py` + `@rule` | Hayır |
| Sohbet tool'u | `agent/chat/tools/<dosya>.py` + `@tool` | Hayır |
| UI sekmesi | `ui/tab_<ad>.py` + `render()` | `app.py`'ye tek satır |
| Rapor kalıbı | `agent/reports/lexicon.py` | Hayır |
| Eşik | `agent/config/<alan>.py` içinde kendi bölümüne | Hayır |
| Şema alanı (varsayılan değerli) | `agent/schemas/<alan>.py` | Hayır (`[SCHEMA]` PR) |
| Başka model / LLM | `detection/detector.py` / `llm/client.py` | Hayır, tek giriş noktası |
| Başka arayüz (ses vb.) | yeni dosya, `pipeline.run_events` kullanır | Hayır |

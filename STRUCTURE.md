# STRUCTURE — Mimari ve Dosya Yapısı

> Hibrit mimari: **Katman 1** deterministik kanıt hattı + **Katman 2** tool kullanan LLM agent.
> Backend: Python (motor) + Flask (REST API). Frontend: React (ayrı planlanacak; bu dokümanda yalnızca kullanacağı endpoint'ler var).
> Case analizi ve tasarım gerekçeleri için: [CASE.md](CASE.md). Uygulama sırası için: [STEPS.md](STEPS.md).

---

## 1. Veri akışı

```
                 ┌────────────── Katman 1: Kanıt hattı (deterministik, her zaman çalışır) ──────────────┐
detections.json ─┤                                                                                        │
image_meta.json ─┼─► loaders ─► repository ─► matcher (tespit↔track) ─► kinematics ─┐                     │
tracks.csv ──────┤                                                                   ├─► consistency ─► risk ─► dossier (JSON)
zones.json ──────┤                          report extract ─► claim_parser ─► linker ┘                     │
field_reports ───┘                                (LLM + cache)                                            │
                 └────────────────────────────────────────────────────────────────────────────────────────┘
                                                        │
                 ┌────────────── Katman 2: Agent ───────▼───────────────────────────────────────────────────┐
                 │  runner: dossier + system prompt ─► GLM ⇄ tool registry (area / movement / image)        │
                 │          ─► şema doğrulaması ─► Assessment (JSON)   [hata olursa: kural bazlı skor]      │
                 └──────────────────────────────────────────────────────────────────────────────────────────┘
                                                        │
                                  Flask API  ◄──────────┘  ─►  React UI
```

## 2. Dosya ağacı

```
dss-follow/
├── .env                      # Gizli: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL (git'e girmez)
├── .env.example              # .env şablonu (anahtarsız)
├── .gitignore
├── requirements.txt
├── CASE.md  STRUCTURE.md  STEPS.md  FINDINGS.md
│
├── stage2/                   # [SALT OKUNUR] Görev verisi
├── detections_output/        # [SALT OKUNUR] YOLO çıktıları (detections.json, plots/, stage2_final.csv)
│
├── outputs/                  # [ÜRETİLEN, git'e girmez]
│   ├── cache/llm/            # LLM yanıt önbelleği (hash → json)
│   ├── claims.json           # Ayrıştırılmış rapor iddiaları
│   ├── dossiers/<image>.json # Katman 1 çıktısı
│   ├── assessments/<image>.json  # Katman 2 çıktısı
│   └── logs/                 # agent izleri (tool çağrıları), LLM kullanım/maliyet logu
│
└── backend/
    ├── __init__.py
    ├── config.py
    ├── cli.py
    ├── prompts/                  # Tüm LLM prompt'ları (Markdown şablonları, versiyonlanır)
    │   ├── claim_parser.md
    │   ├── vision_inspect.md
    │   └── agent_system.md
    ├── engine/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── pipeline.py
    │   ├── data/
    │   │   ├── __init__.py
    │   │   ├── loaders.py
    │   │   └── repository.py
    │   ├── geo/
    │   │   ├── __init__.py
    │   │   ├── geometry.py
    │   │   └── zones.py
    │   ├── fusion/
    │   │   ├── __init__.py
    │   │   ├── matcher.py
    │   │   └── kinematics.py
    │   ├── reports/
    │   │   ├── __init__.py
    │   │   ├── extract.py
    │   │   ├── claim_parser.py
    │   │   └── linker.py
    │   ├── analysis/
    │   │   ├── __init__.py
    │   │   ├── consistency.py
    │   │   ├── risk.py
    │   │   └── dossier.py
    │   ├── llm/
    │   │   ├── __init__.py
    │   │   ├── client.py
    │   │   ├── cache.py
    │   │   └── prompt_loader.py
    │   └── agent/
    │       ├── __init__.py
    │       ├── prompts.py
    │       ├── schemas.py
    │       ├── runner.py
    │       └── tools/
    │           ├── __init__.py       # registry
    │           ├── area_tools.py
    │           ├── movement_tools.py
    │           └── image_tools.py
    ├── api/
    │   ├── __init__.py
    │   ├── app.py
    │   ├── serializers.py
    │   ├── jobs.py
    │   └── routes/
    │       ├── __init__.py
    │       ├── meta.py
    │       ├── images.py
    │       ├── tracks.py
    │       ├── reports.py
    │       └── analysis.py
    └── tests/
        ├── conftest.py
        ├── test_loaders.py
        ├── test_geometry.py
        ├── test_llm.py
        ├── test_fusion.py
        ├── test_reports.py
        ├── test_analysis.py
        ├── test_agent_tools.py
        ├── test_agent_schema.py
        ├── test_agent_runner.py
        └── test_api.py
```

### UI (React, `ui/`)
Hızlı sonuç odaklı, sade yapı: router yok (hash adresleri), durum yönetimi kütüphanesi yok.
```
ui/
  package.json · vite.config.ts (/api → Flask :5000 proxy) · tsconfig.json · index.html
  src/
    main.tsx                 hash router (#/, #/image/<id>, #/reports) + üst menü + bütçe göstergesi
    api.ts                   API çağrıları + tipler
    risk.ts                  risk renkleri, Türkçe etiketler, yardımcılar
    styles.css               Tailwind + koyu tema temel stiller
    pages/Ops.tsx            TEK EKRAN: olay akışı (sol) · harita (orta, seçili olayın araçları + izleri + raporlar,
                             2 saatlik oynatma çubuğu, rapor anı işaretleri) · detay (sağ: fotoğraf, Değerlendirme/Araç/Raporlar)
    pages/Reports.tsx        137 raporun doğrulama tablosu + kaynak × sonuç matrisi
    components/OpsMap.tsx    Leaflet (soluk altlık): üs, halkalar, bölgeler, olaylar, izler, rapor→araç çizgileri, bölge sektörü
    components/EventList.tsx olay akışı
    components/EventDetail.tsx sağ panel (fotoğraf + 3 sekme)
    components/ChatPanel.tsx Analist Asistanı (sağ alt); aksiyonları 'dss-action' olayıyla Ops'a iletir
    components/AgentTrace.tsx  SSE canlı agent izi
```
Çalıştırma: `.venv/bin/flask --app backend.api.app run --port 5000` ve `cd ui && npm run dev` → http://localhost:5173

## 3. Dosya sorumlulukları

### Kök ve yapılandırma
| Dosya | Sorumluluk |
|---|---|
| `backend/config.py` | `.env` okur. Tek bir `Settings` nesnesi sunar: veri yolları, LLM ayarları, **tüm eşikler** (eşleşme kapısı 5 m, rapor bağlama yarıçapı 150 m, zaman penceresi 120 dk, durağanlık eşiği, risk ağırlıkları, agent iterasyon limiti). Kodda sabit sayı yazılmaz, her eşik buradan okunur. |
| `backend/cli.py` | Komut satırı: `dossier <image|all>`, `assess <image|all>`, `parse-reports`, `budget`. API'den bağımsız debug ve toplu çalıştırma için. |

### `prompts/` — LLM prompt'ları
Prompt'lar koddan ayrı, Markdown şablonu olarak tutulur. Böylece kod değişmeden iyileştirilebilir, sunumda doğrudan gösterilebilir ve `{{değişken}}` yer tutucularıyla doldurulur.

| Dosya | Kullanan | Görev |
|---|---|---|
| `claim_parser.md` | `reports/claim_parser.py` | Tek raporu yapısal iddia JSON'una çevirir. Yalnızca metinde yazanı çıkarır, yorum yapmaz; emin olmadığında `unknown`. Birkaç örnek (few-shot) içerir. |
| `vision_inspect.md` | `agent/tools/image_tools.py` | Kırpılmış görüntü + soru → `{answer, vehicle_type, color, confidence}`. Görmediğini uydurmaz, "belirsiz" diyebilir. |
| `agent_system.md` | `agent/runner.py` | Agent'ın rolü, kanıt hiyerarşisi, karar kuralları, tool kullanım politikası, çıktı şeması, dil kuralları. |

### `engine/` — motor
| Dosya | Sorumluluk |
|---|---|
| `models.py` | Tüm veri tipleri (dataclass) ve enum'lar (`RiskLevel`, `ClaimStatus`, `ClaimType`, `Source`), `to_dict()` ve saat yardımcıları (`parse_hhmm`/`fmt_hhmm`). Temel tipler (`Base`, `Zone`, `ImageMeta`, `Detection`, `Track`, `Report`, `Dataset`) Step 1'de; türetilmiş tipler (`Match`, `Kinematics`, `Claim`, `ClaimCheck`, `VehicleEvidence`, `ImageDossier`, `Assessment`) ait oldukları step'te eklenir. |
| `chat.py` | Analist Asistanı: veri araçları (`find_alerts`, `get_event`, `get_vehicle`, `find_reports`, `zone_activity` + `vehicles_in_area`, `co_movement`) ve UI aksiyonları (`ui_open_event`, `ui_play_track`, `ui_focus_report`, `ui_show_reports`). Prompt: `prompts/chat_system.md`. |
| `pipeline.py` | Motorun dış kapısı: `build_dossier` (bellekte önbellekli), `assess(image_id, force, on_event)` (sonuç `outputs/assessments/`'ta; prompt sürümü değişmediyse önbellekten döner; aynı görüntüye eşzamanlı çağrılar tek çalıştırmada birleşir), `run_all` (4 eşzamanlı). API ve CLI yalnızca bunu çağırır. |
| `data/loaders.py` | Ham dosyaları okuyup `models` tiplerine çevirir. Rapora kararlı ID verir (`R001`…`R137`, dosyadaki sıraya göre). Saati dakikaya çevirir (`"13:25"` → `805`). |
| `data/repository.py` | Bellekte indeksli tek veri deposu (singleton): görüntüye göre tespitler, saate göre track noktaları, `track_at(track_id, t)`, `tracks_ending_at(t)`, `reports_between(t0, t1)`. Diğer tüm modüller veriye buradan erişir. |
| `geo/geometry.py` | Haversine mesafe, kerteriz (bearing), piksel↔lat/lon dönüşümü (PDF formülü), görüntü ayak izi (footprint), nokta-içinde-mi testi, üsse uzaklık. |
| `geo/zones.py` | Noktayı en yakın bölgeye atama. Metinde bölge adı bulma (Türkçe karakter ve büyük/küçük harf normalizasyonu, "Guneybati"/"Güneybatı"). |
| `fusion/matcher.py` | Çekim saatinde tespit ↔ track **birebir atama** (Hungarian, `scipy.optimize.linear_sum_assignment`) + mesafe kapısı. Çıktı: eşleşmeler, track'siz tespitler, tespitsiz track'ler (görüntü içi / dışı ayrımıyla). |
| `fusion/kinematics.py` | Bir track'ten özellikler: anlık ve ortalama hız, yer değiştirme hızı ile yol-uzunluğu hızı, **radyal hız** (üsse göre), ETA, yön, duruş süresi, tortuosity, olaylar (sıçrama, durma, hareket başlangıcı). `track_state_at(t)`: rapor zamanındaki konum ve durum. |
| `reports/extract.py` | Kural tabanlı ön ayrıştırma: koordinat regex'i (`39.9374N 32.8483E`, 4–5 ondalık), bölge adı, kaba kategori (`coordinate` / `zone` / `general`). LLM olmadan çalışır. |
| `reports/claim_parser.py` | Raporu `Claim`'e çevirir: `claim_types`, `vehicle_type`, `count`, `motion`, `stationary_min`, `friendly`, `blanket_friendly`, `color`, `cargo`, `normal_count`, `zone_status`, `hedged`. İki parser: **kurallar** (veri setindeki 32 kalıbı kapsar, LLM'siz) ve **LLM** (`claim_parser.md`, bilinmeyen kalıplara genellenir). Varsayılan mod `llm`: LLM sonucu kullanılır, kurallarla alan alan karşılaştırılır, farklar `parse_notes`'a yazılır; LLM yoksa/geçersizse kurallara düşülür. Koordinat, bölge ve kategori her zaman `extract.py`'den gelir. Sonuç `outputs/claims.json`. |
| `reports/linker.py` | Raporu uzay-zamanda bağlar → `ReportLinks`: görüntüler (ayak izine ≤150 m, rapordan sonraki 120 dk içinde çekilmiş), **rapor saatindeki** konumu koordinata ≤150 m olan track'ler (mesafeyle; ≤60 m "raporun anlattığı araç"), bağlı görüntülerde koordinata yakın tespitler (track'i olmayan park halindekiler dahil), en yakın track mesafesi, bölge. Bölge raporları: o bölgedeki görüntüler + rapor saatinde bölgede kaydı olan track'ler. |
| `analysis/consistency.py` | Her iddiayı gözlemle karşılaştırır: `verified` / `contradicted` / `partial` / `unverifiable`, gerekçe metni ve kanıt referanslarıyla. İddia tipi başına bir kontrol fonksiyonu (sayım, durağanlık, hareket, kimlik, yoğunluk, bölge geneli). |
| `analysis/risk.py` | Özellikleri (yakınlık, radyal hız, ETA, tip, davranış, grup, rapor çelişkisi, dost iddiası) ağırlıklı **temel risk skoruna** (0–100) ve seviyeye (`critical/high/medium/low`) çevirir. Her katkıyı `factors` listesinde açıklar. |
| `analysis/dossier.py` | Katman 1 orkestrasyonu: bir görüntü için yukarıdakileri sırayla çalıştırıp `ImageDossier` üretir (araçlar, eşleşmeler, kinematik, bağlı raporlar, iddia kontrolleri, temel risk, anomaliler, `unknown` iddialar). |
| `llm/client.py` | OpenAI uyumlu istemci: retry/backoff (429/5xx), eşzamanlılık semaforu (4), dakikalık istek limiti, `reasoning_effort`, `reasoning_content` ayrımı, kullanım/maliyet logu, `/key/info` ile bütçe sorgusu, bütçe eşiğinde durdurma. |
| `llm/cache.py` | Disk önbelleği: `sha256(model + messages + tools)` → yanıt. Aynı girdiye ikinci kez para ödenmez, sonuçlar tekrarlanabilir olur. |
| `agent/prompts.py` | Mesaj kurucu: `agent_system.md`'yi yükler, dossier'ı kompakt kullanıcı mesajına çevirir (token tasarrufu), şema düzeltme mesajını üretir. Prompt metni burada değil, `backend/prompts/`'ta durur. |
| `agent/schemas.py` | Agent çıktı şeması (`OUTPUT_SCHEMA_TEXT`), `validate` (enum'lar, temel riski ≥ medium araçların yazılması, sapmada gerekçe, kanıt kimliklerinin veride varlığı, overall ≥ en yüksek seviye), `finalize` (yazılmayan araçları temel seviyeyle ekler), `fallback` (LLM başarısızsa kural tabanlı sonuç). |
| `agent/runner.py` | Agent döngüsü: en fazla 8 iterasyon ve 6 tool çağrısı; son iterasyon (ya da tool hakkı bitince) tool sunulmaz, JSON modu zorlanır. Şema hatasında 1 düzeltme denemesi. Her hata (bozuk yanıt, bütçe freni, ağ, limit) kural tabanlı sonuca düşer ve `trace.fallback` ile işaretlenir. `on_event` ile adımlar (start, llm, reasoning, tool_call, tool_result, repair, done/fallback) yayınlanır. |
| `agent/tools/__init__.py` | Tool registry: `@tool` dekoratörü imza + docstring'den OpenAI şeması üretir; `call(name, args)` argümanları doğrular/dönüştürür ve **hiç exception fırlatmaz** (hata `{"error": ...}` olarak agent'a döner). |
| `agent/tools/area_tools.py` | `vehicles_in_area(lat, lon, radius_m, time_from, time_to, vehicle_type?)`: bir noktada, bir zaman aralığında hangi araçlar vardı (giriş/çıkış, en yakın mesafe, park halindekiler). |
| `agent/tools/movement_tools.py` | `co_movement(track_ids)`: araçlar konvoy / birlikte bekleyen grup / aynı anlarda hareketle buluşan grup mu? Her çift için **tesadüf oranı** (aynı görüntüdeki rastgele çiftlerde bu kadar eşzamanlı hareketin görülme sıklığı) döner. |
| `agent/tools/image_tools.py` | `inspect_image(image_id, target, question)`: görüntüyü kırpıp vision'a sorar (renk, yük/örtü, tip teyidi, kaçırılmış araç). |

**Tool ilkesi:** Tool yalnızca agent'ın **belirsiz** bir durumda kendi kararıyla yapacağı soruşturma içindir: nereye / ne zaman / ne genişlikte bakılacağı ya da hangi hipotezin sınanacağı metinden ve kanıttan çıkarsanır. Deterministik hesaplanabilen her şey (track özeti, bağlı raporlar, bölge raporları, istatistikler) kanıt dosyasındadır; onları tekrar getiren tool yazılmaz.

### `api/` — Flask
| Dosya | Sorumluluk |
|---|---|
| `app.py` | `create_app()`: blueprint kayıtları, CORS (React dev sunucusu için), JSON hata yakalayıcıları, açılışta repository'yi yükleme. |
| `serializers.py` | Motor tiplerini API JSON'una çevirir (alan adları, yuvarlama, `HH:MM` formatı). API sözleşmesi tek yerde tutulur. |
| `jobs.py` | Arka plan iş yöneticisi: `ThreadPoolExecutor(max_workers=4)`, iş durumu (`queued/running/done/failed`), ilerleme, olay kuyruğu (SSE için). |
| `routes/meta.py` | `/health`, `/overview`, `/zones`, `/llm/budget`, `/config` |
| `routes/images.py` | Görüntü listesi, detay, dosya (ham/annotated), tespitler |
| `routes/tracks.py` | Track listesi (zamana/alana göre), track detayı + kinematik |
| `routes/reports.py` | Rapor listesi (filtreli), detay + iddia + bağlantılar + doğrulama durumu |
| `routes/analysis.py` | Dossier, assessment, analiz başlatma, iş durumu, SSE olay akışı, alarm listesi, zaman çizelgesi |

### `tests/`
| Dosya | Kapsam |
|---|---|
| `conftest.py` | Ortak fixture'lar (repository, örnek görüntü `img_000267`) |
| `test_loaders.py` | 40 görüntü, 226 track × 25 nokta, 137 rapor, 323 tespit |
| `test_geometry.py` | **PDF örneği**: (640,394) → 32.86350 / 39.94439; tespit JSON'undaki lat/lon ile tutarlılık |
| `test_fusion.py` | 202 birebir eşleşme, `img_000267_003 ↔ T0045`, T0045 durağan, radyal hız işareti |
| `test_llm.py` | Önbellek anahtarı ve disk önbelleği, prompt şablonu doldurma/hata, LLM sonuç serileştirme (ağsız) |
| `test_reports.py` | Koordinat regex, bölge bulma, rapor→görüntü bağlama (72/72) |
| `test_analysis.py` | 08:50 raporu `verified`, 08:45 "2 kamyon" `partial`, `img_003201` çelişkileri |
| `test_agent_tools.py` | Registry şema üretimi, tool'ların LLM'siz çalışması |
| `test_agent_runner.py` | Sahte (mock) LLM ile döngü: tool çağrısı, iterasyon limiti, şema hatası → düzeltme → fallback |
| `test_api.py` | Endpoint'lerin durum kodları ve şema uyumu (Flask test client) |

## 4. Sözleşmeler

- **Zaman:** API'de `"HH:MM"` (tek gün), içeride dakika (int).
- **ID'ler:** görüntü `img_000267`, tespit `img_000267_003`, track `T0045`, rapor `R001`–`R137` (dosya sırası).
- **Enum'lar İngilizce, UI etiketleri Türkçe:**
  - `risk_level`: `critical | high | medium | low`
  - `claim_status`: `verified | partial | contradicted | unverifiable`
  - `claim_type`: `count | stationary | motion | identity | density | zone_status | noise | unknown`
- **Mesafe** metre, **hız** m/s, **ETA** dakika. `radial_speed_mps < 0` → üsse yaklaşıyor.
- **Katman 1 LLM'siz çalışabilmeli:** `claim_parser` önbellekten veya fallback'ten okur. Dossier her zaman üretilebilir.

## 5. API — React'in kullanacağı endpoint'ler

Temel yol: `/api`. Tüm yanıtlar JSON (görüntü dosyası ve SSE hariç). Hata formatı: `{"error": {"code": "not_found", "message": "..."}}`.

| Metot | Yol | Amaç (UI ekranı) |
|---|---|---|
| GET | `/api/health` | Sağlık kontrolü |
| GET | `/api/overview` | Ana panel: üs, bölgeler, görüntü özetleri, risk dağılımı |
| GET | `/api/zones` | Harita katmanı: üs + bölgeler |
| GET | `/api/images` | Görüntü listesi (filtre: `time_from`, `time_to`, `zone`, `min_risk`) |
| GET | `/api/images/<id>` | Görüntü detayı: meta + tespitler + eşleşmeler |
| GET | `/api/images/<id>/file?variant=raw\|annotated` | JPG dosyası |
| GET | `/api/images/<id>/dossier` | Katman 1 kanıt dosyası |
| GET | `/api/images/<id>/assessment` | Katman 2 sonucu (yoksa 404) |
| POST | `/api/images/<id>/assess` | Agent analizi başlat → iş (202) |
| POST | `/api/assess` | Toplu analiz başlat → iş (202) |
| GET | `/api/jobs/<job_id>` | İş durumu / ilerleme |
| GET | `/api/jobs/<job_id>/events` | **SSE**: agent adımları canlı akış |
| GET | `/api/tracks` | Harita oynatma: `?time=HH:MM` anındaki konumlar veya `?image_id=` |
| GET | `/api/tracks/<track_id>` | Track geçmişi + kinematik |
| GET | `/api/reports` | Rapor listesi (filtre: `source`, `claim_type`, `status`, `image_id`, `zone`, `time_from`, `time_to`) |
| GET | `/api/reports/<report_id>` | Rapor detayı + iddia + bağlantılar + doğrulama |
| GET | `/api/alerts` | Tüm görüntülerde riskli araçlar, önem sırasıyla |
| GET | `/api/timeline` | Zaman çizelgesi: çekimler, raporlar, alarmlar |
| GET | `/api/llm/budget` | Harcanan / kalan bütçe |
| POST | `/api/chat` | Analist Asistanı: `{messages, context}` → `{reply, actions, tools}` |

### Örnek I/O

> Sayılar temsilidir. `img_000267` / `T0045` / `R00x` gibi ID'ler ve tespit değerleri gerçek veriden alınmıştır.

**`GET /api/overview`**
```json
{
  "base": {"name": "Merkez Us", "lat": 39.92184, "lon": 32.85306},
  "zones": [{"name": "Dogu Yolu", "lat": 39.92184, "lon": 32.890542}],
  "time_range": {"from": "08:15", "to": "15:50"},
  "counts": {"images": 40, "detections": 323, "tracks": 226, "reports": 137},
  "risk_summary": {"critical": 2, "high": 5, "medium": 11, "low": 22, "not_assessed": 0},
  "images": [
    {"id": "img_000267", "capture_time": "10:15", "zone": "Dogu Yolu",
     "center": {"lat": 39.920259, "lon": 32.89559}, "dist_to_base_m": 3631,
     "vehicle_count": 6, "max_risk": "medium", "assessed": true}
  ]
}
```

**`GET /api/images/img_000267`**
```json
{
  "id": "img_000267", "capture_time": "10:15", "width_px": 1920, "height_px": 1080,
  "corners": {"top_left": [39.921192, 32.893427], "top_right": [39.921192, 32.897753],
              "bottom_left": [39.919326, 32.893427], "bottom_right": [39.919326, 32.897753]},
  "zone": "Dogu Yolu",
  "urls": {"raw": "/api/images/img_000267/file?variant=raw",
           "annotated": "/api/images/img_000267/file?variant=annotated"},
  "detections": [
    {"id": "img_000267_003", "label": "truck", "confidence": 0.8233,
     "bbox_xywh": [834, 164, 45, 49], "lat": 39.920866, "lon": 32.895357,
     "alt_labels": [], "track_id": "T0045", "match_dist_m": 0.1}
  ],
  "unmatched_tracks": [{"track_id": "T0xxx", "in_frame": false}]
}
```

**`GET /api/images/img_000267/dossier`** (Katman 1 — gerçek çıktıdan kısaltıldı; tam hali `outputs/dossiers/img_000267.json`)
```json
{
  "image_id": "img_000267",
  "capture_time": "10:15",
  "zone": "Dogu Yolu",
  "center": [
    39.920259,
    32.89559
  ],
  "dist_to_base_m": 3631.2,
  "footprint_m": [
    368.9,
    207.5
  ],
  "vehicles": [
    {
      "vehicle_id": "img_000267_003",
      "label": "truck",
      "confidence": 0.8233,
      "lat": 39.920866,
      "lon": 32.895357,
      "dist_to_base_m": 3608.6,
      "zone": "Dogu Yolu",
      "track_id": "T0045",
      "match_dist_m": 0.11,
      "flags": [],
      "kinematics": {
        "state": "stationary",
        "motion": "stationary",
        "dist_to_base_m": 3608.6,
        "radial_change_window_m": -4.4,
        "speed_mps": 0.01,
        "eta_min": null,
        "stationary_min": 120,
        "consistent_approach": false,
        "tortuosity": null,
        "...": "(tam Kinematics nesnesi)"
      },
      "claims": [
        {
          "report_id": "R094",
          "time": "08:45",
          "source": "official",
          "claim_type": "count",
          "status": "partial",
          "reason": "İddia 2 truck; gözlenen 1: T0045 (truck, track, 24 m), T0066 (car, track, 29 m), img_000267_002 (car, park halinde, 14 m).",
          "observed": {
            "claimed": 2,
            "observed": 1,
            "subjects": 3
          },
          "evidence": [
            "report:R094",
            "det:img_000267_003",
            "track:T0045",
            "det:img_000267_001",
            "track:T0066",
            "det:img_000267_002"
          ]
        },
        {
          "report_id": "R094",
          "time": "08:45",
          "source": "official",
          "claim_type": "stationary",
          "status": "verified",
          "reason": "T0045 (truck, track, 24 m): 30 dk durağan; T0066 (car, track, 29 m): 30 dk durağan; tip uyuşmuyor (iddia truck, tespit car); img_000267_002 (car, park halinde, 14 m): track'i yok, park halinde",
          "observed": {
            "required_min": 30
          },
          "evidence": [
            "report:R094",
            "det:img_000267_003",
            "track:T0045",
            "det:img_000267_001",
            "track:T0066",
            "det:img_000267_002"
          ]
        },
        {
          "report_id": "R053",
          "time": "08:50",
          "source": "official",
          "claim_type": "stationary",
          "status": "verified",
          "reason": "T0045 (truck, track, 22 m): kayıt başından (35 dk) beri durağan; T0066 (car, track, 31 m): kayıt başından (35 dk) beri durağan; tip uyuşmuyor (iddia truck, tespit car); img_000267_002 (car, park halinde, 14 m): track'i yok, park halinde",
          "observed": {
            "required_min": 60
          },
          "evidence": [
            "report:R053",
            "det:img_000267_003",
            "track:T0045",
            "det:img_000267_001",
            "track:T0066",
            "det:img_000267_002"
          ]
        },
        {
          "report_id": "R083",
          "time": "08:50",
          "source": "official",
          "claim_type": "identity",
          "status": "contradicted",
          "reason": "Dost iddiası şüpheli: tip uyuşmuyor (iddia car, tespit truck); hareket iddiası (approaching_base) gözlemle çelişiyor.",
          "observed": {},
          "evidence": [
            "report:R083",
            "det:img_000267_003",
            "track:T0045"
          ]
        },
        {
          "report_id": "R083",
          "time": "08:50",
          "source": "official",
          "claim_type": "motion",
          "status": "contradicted",
          "reason": "T0045 (truck, track, 53 m): rapordan çekime üsse uzaklık -18 m; rapor anında stationary",
          "observed": {
            "claimed_motion": "approaching_base"
          },
          "evidence": [
            "report:R083",
            "det:img_000267_003",
            "track:T0045"
          ]
        }
      ],
      "baseline_risk": {
        "score": 35,
        "level": "medium",
        "factors": [
          {
            "name": "heavy_vehicle",
            "weight": 15,
            "detail": "ağır araç (truck)"
          },
          {
            "name": "report_contradiction",
            "weight": 10,
            "detail": "çelişen rapor: R083"
          },
          {
            "name": "unverified_friendly_claim",
            "weight": 10,
            "detail": "dost/ikmal iddiası gözlemle çelişiyor: R083"
          }
        ]
      }
    },
    "... (görüntüdeki diğer araçlar, risk skoruna göre sıralı)"
  ],
  "reports": [
    {
      "report_id": "R094",
      "time": "08:45",
      "source": "official",
      "text": "39.9209N 32.8953E yakininda 2 kamyonun durdugu bildirildi.",
      "claim_types": [
        "count",
        "stationary"
      ],
      "checks": "[... ClaimCheck ...]"
    },
    "..."
  ],
  "context_reports": "[... bölge raporları + konumsuz dost duyuruları ...]",
  "anomalies": [
    {
      "type": "possible_missed_detection",
      "detail": "T0057 çekim anında görüntü içinde ama eşleşen tespit yok (model kaçırmış olabilir).",
      "evidence": [
        "track:T0057"
      ]
    }
  ],
  "max_risk": "medium",
  "risk_counts": {
    "critical": 0,
    "high": 0,
    "medium": 2,
    "low": 4
  }
}
```

**`POST /api/images/img_000267/assess`**
```json
// istek
{"force": false, "reasoning_effort": "low"}
// yanıt 202
{"job_id": "job_7f3a", "status": "queued", "events_url": "/api/jobs/job_7f3a/events"}
```

**`GET /api/jobs/job_7f3a/events`** (SSE, `text/event-stream`)
```
event: step
data: {"type": "tool_call", "tool": "co_movement", "args": {"track_ids": ["T0028", "T0001", "T0135"]}, "iteration": 1}

event: step
data: {"type": "tool_result", "tool": "co_movement", "summary": "T0028–T0001 converged_in_step (4 eşzamanlı hareket, tesadüf %5)"}

event: done
data: {"assessment_url": "/api/images/img_000267/assessment"}
```

**`GET /api/images/img_000267/assessment`** (Katman 2)
```json
{
  "image_id": "img_000267", "model": "glm-5.3-flash", "created_at": "2026-09-27T10:12:00Z",
  "overall_risk": "medium",
  "summary": "Doğu Yolu'nda 2 saattir yerinden ayrılmayan bir kamyon var; hakkındaki '2 kamyon' raporu kısmen çelişkili.",
  "vehicles": [
    {"detection_id": "img_000267_003", "track_id": "T0045", "risk_level": "medium",
     "baseline_level": "medium", "override_reason": null,
     "rationale": "Kamyon üsse 3,6 km mesafede 2 saattir sabit. Durağanlık raporu doğrulandı; '2 kamyon' iddiası kısmen çelişkili.",
     "evidence": ["det:img_000267_003", "track:T0045", "report:R053", "report:R094"]}
  ],
  "attention_items": [
    {"title": "Raporla sayı uyuşmazlığı", "risk_level": "low",
     "rationale": "08:45 raporu 2 kamyon diyor; görüntüde ve track'lerde yalnızca T0045 var.",
     "evidence": ["report:R094", "det:img_000267_003", "track:T0045"]}
  ],
  "trace": {"iterations": 3, "tool_calls": 4, "tokens": {"input": 9120, "output": 1480}, "fallback": false}
}
```

**`GET /api/tracks?time=10:15`**
```json
{"time": "10:15", "points": [{"track_id": "T0045", "lat": 39.920866, "lon": 32.895357,
  "label": "truck", "image_id": "img_000267", "state": "stationary", "risk_level": "medium"}]}
```

**`GET /api/tracks/T0045`**
```json
{"track_id": "T0045", "image_id": "img_000267", "detection_id": "img_000267_003",
 "points": [{"time": "08:15", "lat": 39.921001, "lon": 32.895445, "dist_to_base_m": 3615.7}],
 "kinematics": {"state": "stationary", "motion": "stationary", "stationary_min": 120,
                "radial_speed_mps": -0.0, "consistent_approach": false,
                "segments": [{"kind": "stop", "start": "08:15", "end": "10:15", "duration_min": 120,
                              "distance_m": 0.0, "radial_change_m": -7.1}]}}
// kinematics: GET /api/images/<id>/dossier içindekiyle aynı Kinematics nesnesi (burada kısaltıldı)
```

**`GET /api/reports?image_id=img_000267`**
```json
{"total": 3, "items": [
  {"id": "R053", "time": "08:50", "source": "official", "text": "...",
   "category": "coordinate", "coord": {"lat": 39.92087, "lon": 32.89536},
   "claim": {"claim_type": "stationary", "vehicle_type": "truck", "stationary_minutes": 60},
   "links": {"images": ["img_000267"], "tracks": ["T0045"], "zone": "Dogu Yolu"},
   "status": "verified"}
]}
```

**`GET /api/alerts?min_risk=high`**
```json
{"items": [{"image_id": "img_0xxxxx", "capture_time": "14:55", "detection_id": "img_0xxxxx_002",
  "track_id": "T0xxx", "label": "truck", "risk_level": "critical", "dist_to_base_m": 1620,
  "eta_min": 4, "headline": "Üsse yaklaşan kamyon, 'ikmal aracı' iddiasıyla çelişiyor"}]}
```

**`GET /api/timeline`**
```json
{"events": [
  {"time": "08:45", "kind": "report", "id": "R094", "source": "official", "status": "partial"},
  {"time": "10:15", "kind": "capture", "id": "img_000267", "max_risk": "medium"},
  {"time": "10:15", "kind": "alert", "id": "img_000267_003", "risk_level": "medium"}
]}
```

**`GET /api/llm/budget`**
```json
{"spend_usd": 0.42, "max_budget_usd": 15.0, "remaining_usd": 14.58}
```

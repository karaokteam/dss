# STEPS — Motor + API Uygulama Planı

> Dosya yapısı ve sorumluluklar: [STRUCTURE.md](STRUCTURE.md). Gerekçeler: [CASE.md](CASE.md).

## Kurallar
- Her step **en fazla 5–6 yeni dosya** içerir. Boş `__init__.py` paket işaretleri bu sayıma dahil değildir ve Step 0'da topluca açılır.
- Her step ya bağımsızdır ya da yalnızca **kendinden önceki** step'lere bağımlıdır.
- Her step'in **kabul kriteri** vardır. Kriter geçmeden sonraki step'e geçilmez (`pytest` yeşil + belirtilen kontrol).
- Eşik ve sabitler yalnızca `config.py`'de tutulur.
- Katman 1 (Step 1–6) **LLM anahtarı olmadan da** çalışır.

## Bağımlılık haritası

```
0 ─► 1 ─► 2 ─► 3 ─────────┐
│                          ├─► 5 ─► 6 ─► 7 ─► 8 ─► 9 ─► 10 ─► 11
└─► 4 (LLM, bağımsız) ─────┘
```

---

## Step 0 — Proje iskeleti
**Bağımlılık:** yok

| Dosya | İçerik |
|---|---|
| `requirements.txt` | `flask`, `flask-cors`, `openai`, `python-dotenv`, `numpy`, `scipy`, `pillow`, `pytest` |
| `.env.example` | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY=` (boş) |
| `.gitignore` | `.env`, `outputs/`, `__pycache__/`, `.venv/`, `__MACOSX/`, `.DS_Store` |
| `backend/config.py` | `Settings` dataclass: yollar (`stage2/`, `detections_output/detections_output/detections.json`, `outputs/`), LLM ayarları, eşikler |
| `backend/tests/conftest.py` | `settings` fixture'ı, test verisi yolu |

\+ tüm paketler için boş `__init__.py`.

**Kabul:** `pip install -r requirements.txt` sorunsuz. `python -c "from backend.config import settings; print(settings)"` yolları doğru basıyor.

---

## Step 1 — Veri modeli ve yükleme
**Bağımlılık:** 0

| Dosya | İçerik |
|---|---|
| `backend/engine/models.py` | Dataclass'lar ve enum'lar (bkz. STRUCTURE §3) |
| `backend/engine/data/loaders.py` | 5 kaynağın okunması, rapor ID'leri (`R001…`), saat↔dakika çevirisi |
| `backend/engine/data/repository.py` | İndeksli bellek deposu, `track_at`, `tracks_ending_at`, `reports_between`, `detections_for` |
| `backend/tests/test_loaders.py` | Sayım testleri |

**Kabul:** 40 görüntü, 323 tespit, 226 track (her biri 25 nokta), 137 rapor. Her track'in son saati bir görüntünün çekim saatine eşit.

---

## Step 2 — Coğrafya
**Bağımlılık:** 1

| Dosya | İçerik |
|---|---|
| `backend/engine/geo/geometry.py` | Haversine, bearing, piksel↔lat/lon, footprint, içerde-mi testi, üsse uzaklık |
| `backend/engine/geo/zones.py` | En yakın bölge ataması, metinde bölge adı bulma (normalizasyonlu) |
| `backend/tests/test_geometry.py` | PDF örneği ve tespit JSON'u tutarlılığı |

**Kabul:** PDF örneği (640, 394) → lon 32.86350 / lat 39.94439 (±1e-5). 323 tespitin tümünde, bizim hesapladığımız merkez koordinat ile `detections.json`'daki lat/lon arasındaki fark < 1 m. "Guneybati Yolu" ve "Güneybatı Yolu" aynı bölgeye çözülüyor.

---

## Step 3 — Füzyon: eşleştirme ve kinematik
**Bağımlılık:** 1, 2

| Dosya | İçerik |
|---|---|
| `backend/engine/fusion/matcher.py` | Hungarian + mesafe kapısı. Eşleşmeler, track'siz tespitler, tespitsiz track'ler (görüntü içi/dışı) |
| `backend/engine/fusion/kinematics.py` | Hız (yer değiştirme / yol uzunluğu), radyal hız, ETA, duruş süresi, tortuosity, olaylar (sıçrama, durma, hareket başlangıcı), `track_state_at(t)`, tutarlı yaklaşma |
| `backend/tests/test_fusion.py` | Eşleşme sayıları, örnek araçlar |

**Kabul:**
- 202 birebir eşleşme (kapı 5 m).
- 24 tespitsiz track'in 20'si görüntü dışında, 4'ü içinde.
- `img_000267_003 ↔ T0045`, T0045 `stationary` ve `stationary_min ≥ 110`.
- Durağanlık, noktaların 10–25 m'lik gürültüsünden etkilenmiyor (pencere bazlı yer değiştirme ile ölçülüyor).

---

## Step 4 — LLM altyapısı *(bağımsız, 1–3 ile paralel yapılabilir)*
**Bağımlılık:** 0

| Dosya | İçerik |
|---|---|
| `backend/engine/llm/client.py` | Retry/backoff, semafor(4), dakikalık istek limiti, `reasoning_effort`, kullanım/maliyet logu, `/key/info` ile bütçe sorgusu, bütçe eşiğinde durdurma |
| `backend/engine/llm/cache.py` | `sha256` anahtarlı disk önbelleği |
| `backend/engine/llm/prompt_loader.py` | `backend/prompts/*.md` şablonlarını yükleme, `{{değişken}}` doldurma, prompt hash'i |
| `backend/cli.py` | `ping` (tek "Merhaba" isteği), `budget` komutları. Sonraki step'lerde yeni komutlarla genişletilir. |
| `backend/tests/test_llm.py` | Ağ gerektirmeyen testler: önbellek, prompt şablonu, sonuç ayrıştırma |

**Kabul:** `python -m backend.cli ping` yanıt dönüyor. İkinci çağrı önbellekten geliyor (maliyet 0). `budget` harcanan ve kalan tutarı gösteriyor. Anahtar yoksa açık bir hata mesajı veriyor. `prompt_loader` eksik değişkende hata veriyor.

---

## Step 5 — Rapor ayrıştırma ve bağlama
**Bağımlılık:** 1, 2, 3, 4

| Dosya | İçerik |
|---|---|
| `backend/engine/reports/extract.py` | Koordinat regex'i, bölge adı, kaba kategori (`coordinate / zone / general`) |
| `backend/engine/reports/claim_parser.py` | LLM ile yapısal iddia çıkarımı (JSON şemalı, önbellekli, `outputs/claims.json`) + kural bazlı fallback |
| `backend/engine/reports/linker.py` | Rapor → görüntü (footprint + yarıçap + zaman penceresi), → track (rapor saatindeki konum), → bölge |
| `backend/prompts/claim_parser.md` | İddia çıkarım prompt'u (şema + few-shot örnekler) |
| `backend/tests/test_reports.py` | Regex, kategori ve bağlama testleri |

\+ `cli.py`'ye `parse-reports` komutu eklenir.

**Kabul:**
- 72 koordinatlı / 43 bölgeli / 22 genel rapor ayrımı.
- 72 koordinatlı raporun **72'si** bir görüntüye bağlanıyor.
- Tüm raporlar ayrıştırılıyor: maliyet ~137 kısa istek. Anahtar yoksa fallback ile sınıflandırılamayanlar `unknown` oluyor.
- 08:50 durağanlık raporu → `T0045`.

---

## Step 6 — Analiz ve kanıt dosyası (Katman 1 tamam)
**Bağımlılık:** 1–5

| Dosya | İçerik |
|---|---|
| `backend/engine/analysis/consistency.py` | İddia tipi başına doğrulama → `verified / partial / contradicted / unverifiable` + gerekçe + kanıt referansları |
| `backend/engine/analysis/risk.py` | Ağırlıklı temel skor (0–100), seviye ve `factors` |
| `backend/engine/analysis/dossier.py` | `build_dossier(image_id)` → `ImageDossier` |
| `backend/tests/test_analysis.py` | Bilinen vakalar |

\+ `cli.py`'ye `dossier <image|all>` komutu eklenir.

**Kabul:**
- 40 dossier LLM çağrısı olmadan üretiliyor (`outputs/dossiers/`).
- 08:50 raporu `verified`, 08:45 "2 kamyon" raporu `partial`.
- `img_003201` raporları arasındaki tip ve hareket çelişkisi dossier'da görünüyor.
- Doğrulanmamış dost iddiaları riski düşürmüyor.
- **Elle inceleme:** en yüksek temel skorlu 5 görüntü mantıklı mı? (Eşikler burada kalibre edilir.)

---

## Step 7 — Agent tool'ları (belirsizlik soruşturmaları)
**Bağımlılık:** 1–6

**İlke:** Tool yalnızca agent'ın belirsiz bir durumda karar vereceği soruşturmalar içindir. Deterministik veri kanıt dosyasındadır.

| Dosya | İçerik |
|---|---|
| `backend/engine/agent/tools/__init__.py` | `@tool` registry, imza + docstring'den şema, hata güvenli `call(name, args)` |
| `backend/engine/agent/tools/area_tools.py` | `vehicles_in_area`: bulanık konum/zaman ("civarında", araç yer değiştirmiş olabilir) için esnek alan sorgusu |
| `backend/engine/agent/tools/movement_tools.py` | `co_movement`: konvoy / koordineli yaklaşma hipotezi, tesadüf oranıyla |
| `backend/tests/test_agent_tools.py` | Şema, hata güvenliği, R007/R101/img_003464 vakaları |

**Kabul:** Registry geçerli OpenAI şemaları üretiyor; `call` hiçbir girdide exception fırlatmıyor; çıktılar kısa ve sınırlı (en fazla 25 öğe). ✅

---

## Step 8 — Prompt'lar, çıktı şeması ve vision tool'u
**Bağımlılık:** 4, 7

| Dosya | İçerik |
|---|---|
| `backend/prompts/agent_system.md` | Agent system prompt'u (bkz. aşağıdaki ilkeler) |
| `backend/prompts/vision_inspect.md` | Kırpılmış görüntü sorgu prompt'u |
| `backend/engine/agent/prompts.py` | Mesaj kurucu: system + kompakt dossier mesajı + şema düzeltme mesajı |
| `backend/engine/agent/schemas.py` | `Assessment` şeması ve doğrulayıcısı |
| `backend/engine/agent/tools/image_tools.py` | `inspect_image` (vision): renk, yük/örtü, tip teyidi, kaçırılmış araç |

**Kabul:**
- `img_000267` için kurulan mesajın token sayısı makul (< ~6k).
- `inspect_image` `img_000267_003` için "truck" benzeri bir cevap veriyor.
- Şema doğrulayıcısı eksik alanlı örnek çıktıyı reddediyor.
- ✅ Gerçekleşen: en büyük mesaj ~12 bin karakter (~5k token); `img_000267` tek seferlik denemede ilk yanıt şemaya uydu (54 sn, 0,002 USD).
  Ek olarak kanıt dosyasına kaçırılmış araç adayları (A6) ve genel tablo (A5) eklendi; `tests/test_agent_schema.py`.

**Agent prompt ilkeleri:**
1. **Rol:** üs savunma analisti. Amaç: dikkat gerektiren durumları bulmak, gerekçelendirmek ve dayanak göstermek.
2. **Kanıt hiyerarşisi:** tespit > track > rapor. Çelişkide tespit esas alınır.
3. **Karar kuralları:** Dost/ikmal iddiası doğrulanmadan riski düşürmez; çelişen dost iddiası şüphe sinyalidir. Temel skordan sapmak serbest, ama gerekçe zorunlu.
4. **Uydurma yasağı:** Sayı, ID ve konum yalnızca dossier'dan veya tool sonuçlarından alınır. Her iddia bir kanıt ID'siyle (`det:` / `track:` / `report:`) bağlanır.
5. **Tool politikası:** Dossier yeterliyse tool çağrılmaz. Belirsizlik, `unknown` iddia ya da görüntü içinde tespitsiz track varsa çağrılır. Üst sınır N çağrıdır.
6. **Çıktı:** yalnızca şemaya uygun JSON. Gerekçeler Türkçe, anahtarlar İngilizce.

---

## Step 9 — Agent döngüsü ve pipeline (Motor tamam)
**Bağımlılık:** 1–8

| Dosya | İçerik |
|---|---|
| `backend/engine/agent/runner.py` | Döngü, iterasyon limiti, şema doğrulaması + 1 düzeltme denemesi, fallback, `on_event` |
| `backend/engine/pipeline.py` | `build_dossier`, `assess`, `run_all`. `outputs/` okuma/yazma |
| `backend/tests/test_agent_runner.py` | Sahte LLM ile döngü, limit ve fallback testleri |

\+ `cli.py`'ye `assess <image|all>` komutu eklenir.

**Kabul:**
- `img_000267` uçtan uca değerlendiriliyor. Gerekçede tespit, track ve rapor ID'leri geçiyor.
- 40 görüntünün toplu çalıştırması eşzamanlılık 4 ile tamamlanıyor. Harcanan bütçe loglanıyor (hedef < 1 USD).
- Bozuk LLM yanıtında sonuç `fallback: true` ile kural bazlı dönüyor.
- **Elle inceleme:** `img_003201`, `img_000267` ve en yüksek riskli 3 görüntünün gerekçeleri okunur, prompt iyileştirilir (kod değil, yalnızca `backend/prompts/` değişir).

---

## Step 10 — Flask API: temel
**Bağımlılık:** 1–9

| Dosya | İçerik |
|---|---|
| `backend/api/app.py` | `create_app()`, CORS, hata yakalayıcılar, açılışta repository yükleme |
| `backend/api/serializers.py` | Motor tipleri → API JSON |
| `backend/api/routes/meta.py` | `/health`, `/overview`, `/zones`, `/llm/budget`, `/config` |
| `backend/api/routes/images.py` | `/images`, `/images/<id>`, `/images/<id>/file`, `/images/<id>/dossier`, `/images/<id>/assessment` |
| `backend/api/routes/tracks.py` | `/tracks?time=`, `/tracks?image_id=`, `/tracks/<id>` |

**Kabul:** ✅ `.venv/bin/flask --app backend.api.app run --port 5000` ayağa kalkıyor. Endpoint'ler STRUCTURE §5'teki örnek şemalarla uyumlu. `/images/<id>/file?variant=annotated` `plots/` altındaki görseli dönüyor.

---

## Step 11 — Flask API: analiz, raporlar, işler (Backend tamam)
**Bağımlılık:** 10

| Dosya | İçerik |
|---|---|
| `backend/api/jobs.py` | ThreadPool iş yöneticisi, durum, olay kuyruğu |
| `backend/api/routes/reports.py` | `/reports` (filtreler), `/reports/<id>` |
| `backend/api/routes/analysis.py` | `POST /images/<id>/assess`, `POST /assess`, `/jobs/<id>`, `/jobs/<id>/events` (SSE), `/alerts`, `/timeline` |
| `backend/tests/test_api.py` | Durum kodları ve şema uyumu |

**Kabul:** ✅ `POST assess` 202 dönüyor. SSE akışında tool adımları canlı görünüyor. Aynı görüntü için eşzamanlı iki istek tek iş olarak birleşiyor. `/alerts` önem sırasıyla dönüyor. `pytest` tamamen yeşil.

---

## Sonra: UI/UX
✅ Backend Step 11'de bitti (113 test). Çalıştırma: `.venv/bin/flask --app backend.api.app run --port 5000`.
 React planlaması STRUCTURE §5'teki endpoint'ler üzerine yapılacak.
Aday ekranlar: harita (üs, bölgeler, zaman kaydırıcılı track oynatma), görüntü inceleme (kutular + track + raporlar), alarm listesi, rapor doğrulama tablosu, agent canlı izi (SSE).

# KOD TURU — Mimari akış, dosya dosya

> Kod sunumu için çalışma notu. Veri girişten ekrana kadar hangi dosyada ne yapıyoruz, LLM nerede ve neden devreye giriyor, "belirsizlik" ne demek?
> Ayrıntılı gerekçeler: `MIMARI.md`; kararlar ve bulgular: `FINDINGS.md`.

---

## 0. Tek cümlelik özet

**Kesin hesaplanabilen her şeyi kodla hesaplayıp bir "kanıt dosyası"na koyuyoruz (Katman 1). LLM ajanı bu dosyayı okuyor; sadece kodun karar veremeyeceği, yoruma açık noktalarda araç (tool) çağırıyor ve her cümlesini bir kanıt kimliğine bağlıyor (Katman 2). Ajanın cevabını yine kod denetliyor.**

```
 stage2/ (ham veri)
    │
    ▼
 data/loaders.py ─► data/repository.py              (1) veriyi oku, indeksle
    │
    ├─► geo/geometry.py, geo/zones.py               (2) piksel→koordinat, mesafe, bölge
    ├─► fusion/matcher.py                           (3) tespit ↔ track eşleşmesi
    ├─► fusion/kinematics.py                        (4) hareket: yaklaşma, duruş, ETA, TUR
    ├─► reports/extract.py + claim_parser.py        (5) rapor → yapısal iddia   [LLM #1: ayrıştırıcı]
    ├─► reports/linker.py                           (6) rapor → görüntü / araç / bölge
    ├─► analysis/consistency.py                     (7) iddia doğru mu?
    ├─► analysis/risk.py                            (8) açıklamalı risk skoru
    └─► analysis/dossier.py                         (9) KANIT DOSYASI (görüntü başına)
                │                                        ─── Katman 1 burada biter (LLM'siz) ───
                ▼
 agent/prompts.py → agent/runner.py ⇄ agent/tools/*  (10) ajan döngüsü      [LLM #2: ajan, #3: görsel]
                │
 agent/schemas.py                                    (11) doğrulama / yedek sonuç
                │
 pipeline.py ─► cli.py  |  api/ (Flask) ─► ui/ (React)   (12–14) dış kapı, API, ekran
                              └► engine/chat.py          (15) Analist Asistanı   [LLM #4: sohbet]
```

LLM'in kullanıldığı **dört** yer var ve hepsi ayrı bir prompt dosyasından gelir (`backend/prompts/*.md`):

| # | Nerede | Prompt | Ne için |
|---|---|---|---|
| 1 | `reports/claim_parser.py` | `claim_parser.md` | Serbest metin raporu yapısal iddiaya çevirmek (kurallarla çapraz kontrol edilir) |
| 2 | `agent/runner.py` | `agent_system.md` | Görüntü başına risk değerlendirmesi (tool kullanan ajan) |
| 3 | `agent/tools/image_tools.py` | `vision_inspect.md` | Ajanın istediği fotoğraf kırpmasına bakmak |
| 4 | `engine/chat.py` | `chat_system.md` | Operatörün sorularını cevaplayan asistan |

---

## 1. Ayar ve veri: `backend/config.py`, `engine/models.py`, `engine/data/`

| Dosya | Ne yapıyor | Sunumda söylenecek |
|---|---|---|
| `backend/config.py` | Tüm eşikler tek yerde: eşleşme kapısı 5 m, hareket eşiği 60 m, "tur" tanımı, risk ağırlıkları, ajan limitleri (8 iterasyon, 6 tool) | "Sihirli sayı kodun içinde değil; hepsi burada ve gerekçesi yorumda." |
| `engine/models.py` | Tüm veri tipleri (`Detection`, `Track`, `Report`, `Claim`, `ClaimCheck`, `Kinematics`, `ImageDossier`...) değişmez dataclass olarak | "Modüller birbirine dict değil tipli nesne veriyor." |
| `engine/data/loaders.py` | Ham JSON/CSV'yi okur. **Veriye dokunan tek dosya.** | Veri formatı değişirse yalnızca bu dosya değişir. |
| `engine/data/repository.py` | Bellekte indeksli, salt okunur depo: `tracks_for_image`, `track_at(t)`, `tracks_active_at(t)`, `reports_between` | Diğer her modül veriye buradan erişir. |

---

## 2. Geometri: `engine/geo/geometry.py`, `engine/geo/zones.py`

- `pixel_to_latlon`: Görev tanımındaki **doğrusal oranlama**. Pikselin görüntüdeki oranı köşe koordinatları arasına aynen uygulanır; açı ya da projeksiyon hesabı yapılmaz. Verilen koordinatlarla 323 tespitte fark < 0,07 m.
- `distance_m` (haversine), `dist_to_base_m`, `bearing_deg`: Tüm mesafeler kuş uçuşu. Yol ağı bilinçli olarak kullanılmadı, çünkü 5 dakikalık sıçramalı track'lerde yola eşleme belirsiz.
- `zones.py`: Metinde bölge adını bulur (Türkçe karakter normalizasyonu) ve bir noktanın en yakın bölgesini verir.

---

## 3. Füzyon: `engine/fusion/matcher.py`

**Sorun:** Hangi track'in fotoğraftaki hangi araca ait olduğu verilmiyor.
**Çözüm:** Track'in son noktası, aracın fotoğraftaki yeridir. Çekim saatinde biten track'ler ile tespitler arasında mesafe matrisi kurulur ve **Hungarian (birebir) atama** yapılır (`linear_sum_assignment`, kapı 5 m).

- Neden birebir? Yan yana iki araçta "en yakını seç" yaklaşımı aynı track'i iki araca bağlar.
- Sonuç: 202 eşleşme. Eşleşmeyen track = **tespiti olmayan araç**. Örnek T0188 ağacın altında kaldığı için kamera görmemiş; bunu sadece hareket kaydı sayesinde yakalıyoruz.

---

## 4. Kinematik: `engine/fusion/kinematics.py`

`compute_kinematics(track, base)` her track için şunları hesaplar:

| Çıktı | Tanım |
|---|---|
| hareket / bekleme adımları | 5 dakikada ≥ 60 m yer değiştirme "hareket" sayılır. Veride araçlar bekleyip sıçrıyor. |
| `motion` | Son 60 dakikada üsse yaklaşma / uzaklaşma / durma |
| **`consistent_approach`** | En az 3 hareket ve **hepsi** üsse yaklaştırıyor. 226 araçtan yalnızca **7**'sinde var. |
| **`circling`** (`_circling`) | Ardışık ≥ 3 noktada üsse uzaklık ±30 m bant içinde, < 1,5 km, açısal tarama ≥ 120°. **5** araç (T0043, T0158, T0172, T0198, T0034). Tur fotoğraflar arasında olur; fotoğrafta görünmez. |
| `eta_min` | Yalnızca hâlâ hareket eden araç için |
| `min_dist_to_base_m` | Kayıt içinde üsse en yakın geçiş |

- `track_state_at(track, base, t)`: Aracın t anındaki durumunu **yalnızca o ana kadarki kayıtla** hesaplar. Rapor doğrulamada gelecek bilgisi sızmaz.
- `move_steps`, `same_direction_sync`, `sync_chance_table`: "Birlikte hareket" sınaması için. Rastgele araç çiftlerinin ne sıklıkla tesadüfen senkron hareket ettiğini de hesaplar (tesadüf oranı).

---

## 5. Rapor ayrıştırma: `engine/reports/extract.py`, `engine/reports/claim_parser.py` [LLM #1]

1. `extract.py` (kural): Koordinat, bölge adı, kategori, araç tipi, sayı ve renk regex ile çıkarılır. **Sayı kopyalama işi LLM'e verilmez.**
2. `claim_parser.py`:
   - `parse_llm`: GLM rapor metnini `Claim`'e çevirir. İddia tipi (sayım / durağanlık / hareket / kimlik-dost / yoğunluk / bölge durumu / gürültü), hareket yönü, dost iddiası ve çekinceler çıkarılır.
   - `parse_rules`: Aynı işi kurallarla yapar.
   - `compare`: İkisini karşılaştırır; uyuşmazlık `parse_notes`'a yazılır. Sonuç: **137/137 uyum**.
   - LLM yoksa ya da bozuk yanıt verirse kurallara düşer.
3. Sonuç `outputs/claims.json`'a yazılır: `python -m backend.cli parse-reports`.

> **Neden hibrit?** Kurallar bu veri setini kapsıyor ve test edilebilir. LLM, yarın gelecek farklı bir rapor kalıbına genellenebilir. Çapraz kontrol ikisinin de yanlışını yakalar.

---

## 6. Rapor bağlama: `engine/reports/linker.py`

- **Koordinatlı rapor:** Koordinat, aracın **fotoğraftaki** konumudur. 5 ondalıklı koordinatların 31/35'i fotoğraftaki araca ≤ 3 m; rapor saatindeki konuma yakın olan 0/35.
  - Görüntü: rapordan sonraki 2 saat içinde çekilmiş ve alanı koordinatı içeren fotoğraf.
  - Track'ler: o fotoğrafta biten ve son noktası koordinata yakın olanlar.
- **Bölge raporu:** O bölgedeki görüntüler ve rapor saatinde bölgede kaydı olan track'ler.
- **Genel rapor** (hava, tatbikat): bağlantı yok; yalnızca bağlam.

---

## 7. İddia doğrulama: `engine/analysis/consistency.py` (en önemli dosya)

**Akış:** `check_report(ctx, report)` → iddia tipine göre `_check_*` → `ClaimCheck(status, reason, observed, subjects, evidence)`

1. **Özneyi bul:** `resolve_subjects` / `image_vehicles` fotoğrafta koordinata en yakın aracı bulur. Tolerans koordinat hassasiyetine göre değişir: 5 hane ~3 m, 4 hane ~12 m. Tipi uyan araç tercih edilir.
2. **Davranışa bak:** `behavior(ctx, track, t)` aracın **rapordan önceki 30 dakikasını** özetler. `approach_after` rapordan sonra çekime kadar üsse yaklaşıp yaklaşmadığını söyler.
3. **Tipine göre hükmet:**

| Fonksiyon | İddia | Kural |
|---|---|---|
| `_check_stationary` | "uzun süredir duruyor" | Kaydın kapsamadığı süre varsa "kısmen" |
| `_check_count` | "5 kamyon" | Görülen, iddianın yarısından azsa "çelişkili" |
| `_check_motion` | "üsse ilerliyor / uzaklaşıyor / olağan" | Rapordan önceki 30 dakikayla karşılaştırılır |
| `_check_identity` | "bize bağlı / planlı ikmal" | **Asla "doğrulandı" olmaz.** Araç üsse yaklaşıyorsa `reassuring_on_approach` bayrağı konur. |
| `_check_zone_status` | "bölgede ağır araç yok / olağan" | Rapor anı ve önceki 15 dakikadaki track'ler. Tur atan araç varsa "çelişkili". Yokluk tam doğrulamaz. |

4. Sonuç dört değerden biridir: doğrulandı / kısmen / çelişkili / doğrulanamaz. Yanında sayılı bir gerekçe ve kanıt kimlikleri bulunur.

> **Canlı örnek:** R126 (12:35) "hareketleri olağan". O an T0122 kamyonu gerçekten duruyor, ama rapordan sonra üsse 4,3 km yaklaşıyor. Hüküm: **kısmen + şüphe bayrağı**.
> Kanıt: `python -c "from backend.engine.analysis.consistency import *; ..."` ya da UI'da Raporlar sekmesi.

---

## 8. Risk skoru: `engine/analysis/risk.py`

`score(RiskInput) → BaselineRisk(score 0–100, level, factors[])`. Skordaki her puan adı ve açıklaması olan bir `RiskFactor`'dan gelir:

- **Konum:** üsse < 2 km (+20)
- **Tip:** ağır araç (+15), grup (+10)
- **Hareket:** **üssün etrafında dönme (+35)**, **tutarlı yaklaşma (+20)**, hızlı yaklaşma, ETA < 15 dk, yakın geçiş, uzun bekleme
- **Rapor:** yalnızca `reassuring_claim` (+10). Güven verici iddia çelişiyorsa ya da üsse yaklaşan araca aitse eklenir. **Hiçbir rapor riski düşürmez** (testle korunuyor).

Seviyeler: kritik ≥ 70, yüksek ≥ 50, orta ≥ 25.

---

## 9. Kanıt dosyası: `engine/analysis/dossier.py`

`build_dossier(image_id)` Katman 1'in orkestratörüdür. Bir görüntü için tek bir `ImageDossier` üretir:

- **vehicles:** Tespit ve track, kinematik, o araca ait iddialar, bayraklar (park halinde, düşük güven, kaçırılmış olabilir), eşik altı adaylar, risk faktörleri.
- **reports / context_reports:** Bağlı raporlar ve bölge ya da genel duyurular.
- **anomalies:** `possible_missed_detection`, `circling_base`, `reassuring_claim_on_approach`, `claim_without_vehicle`, `zone_report_mismatch`, `convoy`.
- **global_context:** Çekim anında tüm bölgelerde üsse tutarlı yaklaşan ve üssün etrafında dönen araçlar.

Dışarıya çıkarma: `python -m backend.cli dossier img_000860` → `outputs/dossiers/img_000860.json`.

> **Buraya kadar LLM yok** (ayrıştırılmış iddialar önbellekten geliyor). Aynı girdi her seferinde aynı çıktıyı verir ve 122 testle korunuyor.

---

## 10. Ajan: `engine/agent/` [LLM #2 ve #3]

### 10.1 Girdi: `agent/prompts.py` + `backend/prompts/agent_system.md`
- `dossier_text()` 25 KB'lık JSON'u okunur bir metne sıkıştırır: GENEL TABLO, ARAÇLAR, RAPORLAR, ANOMALİLER.
- `agent_system.md` 11 kural içerir. Örnekler: "dost iddiası riski asla düşürmez", "doğrulanamaz ≠ sahte", "tutarlı yaklaşma yalnızca işaretli araç için", "tesadüf oranı yüksekse koordinasyon deme". Prompt'un sürüm hash'i her sonuca yazılır.

### 10.2 Döngü: `agent/runner.py` → `run_agent()`
```
for iterasyon in 1..8:
    tool hakkı kaldıysa ve son iterasyon değilse → tool'ları sun, değilse JSON modu zorla
    model tool çağırdı mı? → tools.call(...) → sonucu mesaja ekle → devam
    model cevap verdi mi? → normalize_refs → validate
        hata yok   → finalize → BİTTİ
        hata var   → 1 kez düzeltme iste → hâlâ hatalı → fallback (kural tabanlı sonuç)
her türlü istisna (bütçe, ağ, limit) → fallback
```
- **Sonsuz döngü yok:** En fazla 8 iterasyon ve 6 tool çağrısı. Son iterasyon her zaman cevaba ayrılır.
- **Sistem asla sonuçsuz kalmaz:** Fallback, Katman 1 sonucunu döner ve `trace.fallback=true` ile açıkça işaretler.
- Her adım `on_event` ile yayınlanır; UI bunu SSE ile canlı gösterir (AgentTrace bileşeni).

### 10.3 "Belirsizlik" ne demek, hangi tool ne zaman çağrılır?
**İlke (`agent/tools/__init__.py` başındaki yorum):** Kodla hesaplanabilen hiçbir şey tool değildir; hepsi zaten kanıt dosyasında. Tool yalnızca **nereye, ne zaman, neye bakılacağının** kanıttan çıkarım gerektirdiği yerlerde vardır. Yani tool'un parametrelerini ancak bir yorumcu seçebilir.

| Tool (dosya) | Belirsizlik türü | Tipik tetikleyici | Gerçek örnek |
|---|---|---|---|
| **`inspect_image`** (`tools/image_tools.py`) | **Görsel belirsizlik:** Sayılar cevap veremez, fotoğrafa bakmak gerekir. | Düşük güvenli tespit ("gerçekten kamyon mu?"), renk/yük iddiası ("mavi devriye aracı"), tespiti olmayan track ("orada araç var mı, örtülü mü?") | img_000860: T0122 güven **0,10** → "Bu gerçekten kamyon mu, yükü var mı?" → run3: `truck, loaded`; run4: araç seçilemedi. Karar ikisinde de kritik: belirsiz görsel, riski düşürmeye yetmez. |
| **`vehicles_in_area`** (`tools/area_tools.py`) | **Konum/zaman belirsizliği:** Rapor "civarında" diyor, araç bulunamadı ya da yer değiştirmiş olabilir. Nereye, hangi yarıçapla, hangi saatlere bakılacağına ajan karar verir. | Anlatılan araç bulunamayan iddia, "bölgede toplanma var mı?" sorusu | img_001230: R007 noktası çevresinde 1000 m, 13:30–15:15 → araç nereye gitti? |
| **`co_movement`** (`tools/movement_tools.py`) | **Hipotez belirsizliği:** Hangi araçların birlikte değerlendirileceği bir hipotez (konvoy mu, tesadüf mü?). Ajan track'leri seçer, tool 2 saatlik kayıtla sınar ve **tesadüf oranını** döner. | Yan yana duran kamyonlar, "3 araçlık konvoy" raporu, aynı anda yaklaşan araçlar | img_000860: T0122 + 5 araç → senkron hareket 2, `chance_rate 0,43` → "tesadüf, koordinasyon değil" |

- Run4 kullanımı: `inspect_image` 50, `vehicles_in_area` 21, `co_movement` 10 çağrı.
- **Tool kaydı:** `@tool` dekoratörü (`tools/__init__.py`) şemayı fonksiyonun tip ipuçları ve docstring'inden **otomatik** üretir. Yeni tool eklemek = bir fonksiyon yazmak. Argümanlar `_coerce` ile doğrulanır; hatalı argüman modele hata mesajı olarak döner, sistemi çökertmez.
- `inspect_image` içinde: `_target_box` hedefi bulur, `render_crop` hedefi kırmızıyla işaretleyip büyütür, vision modeline `vision_inspect.md` ile sorulur. Cevap şemasında `occluded` alanı var.

### 10.4 Çıktı denetimi: `agent/schemas.py`
`validate(raw, dossier)` kodla şunları kontrol eder:
- Temel riski orta ve üstü olan her araç yazılmış mı?
- Temelden sapan her seviyenin `override_reason`'ı var mı?
- **Her kanıt kimliği (`det:`, `track:`, `report:`) veride gerçekten var mı?** Uydurma kimlik → red.
- "Tutarlı yaklaşma" yalnızca işaretli araç için mi söylenmiş? (Olumsuz cümleler muaf.)
- **Yeni:** Yükseltme gerekçesi yalnızca elenmiş sinyallere mi dayanıyor (tesadüf oranı, "toplanma", "son adımda vardı")? → red.
- "sahte" kelimesi yasak (doğrulanamaz ≠ sahte).
- Genel risk, araçların en yüksek seviyesinden düşük olamaz.

`normalize_refs` küçük biçim hatalarını otomatik düzeltir. `finalize` yazılmayan araçları temel seviyeleriyle ekler. `fallback` kural tabanlı sonucu üretir.

> **Sunum cümlesi:** "Bilinen bir hata türünü prompt'a yalvararak değil, kodla engelliyoruz."

---

## 11. LLM altyapısı: `engine/llm/`

| Dosya | İş |
|---|---|
| `client.py` | OpenAI uyumlu GLM gateway. Eşzamanlılık 4, dakikada 60 istek, 429/5xx'te geri çekilmeli tekrar. **Bütçe freni:** gerçek harcama 13 USD'ye ulaşınca istek atılmaz. Kullanım logu `outputs/logs/llm_usage.jsonl`. |
| `cache.py` | İstek içeriğinin sha256'sı → yanıt. Aynı istek ikinci kez ücretlendirilmez; sonuçlar tekrarlanabilir. |
| `prompt_loader.py` | `prompts/*.md` şablonlarını doldurur ve sürüm hash'i üretir. Prompt değişince eski sonuçlar "eski" sayılır. |

---

## 12. Dış kapı: `engine/pipeline.py`, `backend/cli.py`

- `pipeline.py`: API ve CLI yalnızca bunu çağırır. İçinde `build_dossier`, `assess(image_id, force)` (sonucu `outputs/assessments/<id>.json`'a yazar), `run_all` (paralel) ve `is_current` (prompt sürümü değiştiyse sonuç eskimiştir) var.
- `cli.py` komutları:
  ```
  python -m backend.cli ping | budget
  python -m backend.cli parse-reports
  python -m backend.cli dossier img_000860
  python -m backend.cli assess img_000860 --verbose      # tool çağrılarını canlı gösterir (demo için iyi)
  python -m backend.cli assess all --force
  python -m backend.cli eval                             # ekibin 23 elle etiketiyle ölçüm
  ```

---

## 13. API: `backend/api/` (Flask)

| Dosya | Uç noktalar |
|---|---|
| `app.py` | Uygulama fabrikası, hata yönetimi |
| `routes/images.py` | Görüntü listesi, dosya, dossier ve değerlendirme |
| `routes/tracks.py` | `?image_id=`, `?time=&zone=` (bölge oynatma), `?all=1` (tüm gün) |
| `routes/reports.py` | Raporlar ve doğrulama sonuçları |
| `routes/analysis.py` | `POST /assess` (arka plan işi), `/jobs/<id>/events` (**SSE**, ajanın adımları canlı), `/alerts`, `/timeline`, `/chat` |
| `jobs.py` | İş kuyruğu. Aynı iş varsa yenisi açılmaz. |
| `serializers.py` | Modelleri JSON'a çevirir |

---

## 14. Arayüz: `ui/src/` (React + Vite + Tailwind + Leaflet)

| Dosya | İş |
|---|---|
| `pages/Ops.tsx` | Ana ekran: olay listesi, harita, detay. "Ne görüyorum?" bandı ve olay / tüm gün modları. |
| `components/OpsMap.tsx` | Karanlık harita, SVG araç ikonları, track kuyrukları, bölge sektörü, rapor çizgisi |
| `components/EventDetail.tsx` | Değerlendirme, Araç ve Raporlar sekmeleri (↻ = tur, ⇣⇣ = tutarlı yaklaşma) |
| `components/AgentTrace.tsx` | SSE ile ajanın canlı adımları (hangi tool, ne döndü) |
| `components/ChatPanel.tsx` | Asistan: Markdown cevap + haritada aksiyon |
| `pages/Reports.tsx` | 137 raporun hükümleri |

---

## 15. Analist Asistanı: `engine/chat.py` [LLM #4]

İki tür tool var:
- **Veri tool'ları:** `find_alerts` (`consistent_approach_only`, `circling_only`), `get_event`, `get_vehicle`, `find_reports`, `zone_activity`, `vehicles_in_area`, `co_movement`
- **Ekran tool'ları:** `ui_open_event`, `ui_play_track`, `ui_focus_report`, `ui_highlight_tracks`, `ui_show_reports`. Model bunları çağırınca UI haritayı yönetir.

En fazla 6 iterasyon ve 8 tool çağrısı var; sonsuz döngü yok. Örnek soru: "Üssün etrafında dönen araçları göster" → `find_alerts(circling_only)` → `ui_highlight_tracks([5 track])`.

---

## 16. Kalite: `backend/tests/`, `backend/engine/eval/gold.py`

- **122 test**, LLM'siz ve deterministik. Kapsam: geometri, eşleşme, kinematik, rapor hükümleri, risk, dossier, ajan şeması ve doğrulayıcı, tool'lar, API.
- **Altın küme:** Ekibin elle etiketlediği 23 rapor (`eval/gold_reports.json`). Katman 1 **22/23** uyum.

---

## 17. Kod sunumunda önerilen sıra (≈ 5 dk)

1. `engine/pipeline.py` (15 sn): "Dış kapı bu, iki katman var."
2. `engine/fusion/kinematics.py` → `_circling` ve `consistent_approach` (45 sn): "Tehdit sinyali kodla bulunuyor."
3. `engine/analysis/consistency.py` → `_check_identity` (45 sn): "Kimlik asla doğrulanmaz; yaklaşan araçta şüphe."
4. `outputs/dossiers/img_000860.json` ya da `cli dossier` çıktısı (30 sn): "Ajanın gördüğü tek şey bu."
5. `engine/agent/tools/__init__.py` başlığı + üç tool'un docstring'i (60 sn): "Tool = belirsizlik soruşturması."
6. `engine/agent/runner.py` → `run_agent` döngüsü (45 sn): "Limitler, düzeltme, yedek."
7. `engine/agent/schemas.py` → `validate` (45 sn): "Uydurma kimliği ve elenmiş sinyalle yükseltmeyi kod reddediyor."
8. Canlı: `python -m backend.cli assess img_000860 --force --verbose` ya da UI'daki AgentTrace (30 sn).

## 18. Muhtemel sorular

- **"Neden her şeyi LLM'e vermediniz?"** Sayısal kanıt kesin ve tekrarlanabilir olmalı. LLM sayı kopyalarken ve eşik uygularken hata yapar. Ona yorum işini bıraktık.
- **"LLM uydurursa?"** Her kanıt kimliği veride doğrulanıyor; uydurma kimlik içeren cevap reddediliyor. İki kez hatalı cevapta kural tabanlı sonuç dönüyor.
- **"Sonsuz döngü / maliyet?"** 8 iterasyon ve 6 tool limiti, bütçe freni ve disk önbelleği var. 40 görüntü ≈ 0,15 USD.
- **"Tool'u neden bu üçüyle sınırladınız?"** Kodla hesaplanabilen hiçbir şey tool değil. Bu üçü parametresi yorum gerektiren soruşturmalar.
- **"Nasıl ölçtünüz?"** 122 test, ekibin 23 elle etiketi (22/23) dış gözden geçirmede bulunan 5 açığın kapatılması (FINDINGS §E); ajanın rapor hükümleri 13/23 → 21/23.

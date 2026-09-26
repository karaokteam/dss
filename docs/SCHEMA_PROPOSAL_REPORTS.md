# Şema önerisi: rapor kontrolleri (Kişi 4 → Kişi 5)

**Durum:** Öneri. `dss/schemas.py`'ye henüz dokunulmadı. Kod hazır: `dss/reports/trace.py`, `dss/reports/zone_checks.py`.
**İstenen:** İki opsiyonel alan ve prompta iki kısa paragraf:
- `ReportChecks.trace`: koordinatlı raporlar için (§1–§3).
- `ReportEv.zone_checks`: bölge adıyla yazılmış raporlar için (§5).

## 1. Neden

Mevcut `ReportChecks` rapor noktasına yakın olanlara bakıyor (150 m, ≥30 dk duran track var mı). Veri daha keskin bir şey söylüyor:

- **Rapor belirli bir aracı anlatıyor.** 5 haneli koordinatlar çekim anındaki bir aracın 0–1 m yakınına, 4 haneliler ≤10 m yakınına düşüyor. O aracı track'i üzerinden izlersek iddia, aracın **kendi** hareketiyle ölçülebilir.
- Yakınlık kontrolü bunu kaçırıyor. **R007** ("üsse gelen otomobil bize bağlı") noktasında başka duran araçlar olduğu için rapor uyumlu görünüyor. Oysa anlatılan araç T0131 rapordan önceki 30 dakikada üsten **1,9 km uzaklaşmış**.
- **R113 ve R102** en tehlikeli tuzak: "dost" denen araçlar 30 dakikada üsse 3,2–3,6 km yaklaşıyor. Hareket doğru, kimlik doğrulanamaz.
- Süre iddiaları ("bir saatten uzun süredir") için verinin o sürenin ne kadarını kapsadığı bilinmeli. R053'te 60 dakikanın sadece 35'i veride var.
- **Hayalet raporlar** (R039, R071, üçüncü taraf "yüklü / örtülü ağır araç"): rapor noktasında çekim anında ne araç ne track var.
- **0,25 eşiği kamyon kaçırıyor.** R033'teki kamyon ve img_000860'taki T0122 bu eşiğin altında kalıyor. Hedef araç çekim anındaki track'ten de bulunduğu için `trace` bunları yine yakalıyor.

## 2. Değişiklik

```python
# dss/schemas.py
from dss.reports.trace import ReportTrace      # ya da modeller schemas.py'ye taşınır

class ReportChecks(BaseModel):
    ...                                         # mevcut 4 alan aynen kalır
    trace: Optional[ReportTrace] = None         # rapora özgü ölçümler (Kişi 4)
```

```python
# dss/evidence/builder.py (rapor bölümü, şu an böyle)
reports, context = reports_for(image_id, D)
for r in reports:
    if r.scope == "koordinat":
        r.checks = checks_for(r, dets, cap, D)
        r.checks.trace = trace_for(r, dets, image_id, D)     # ← eklenecek tek satır
```

`ReportTrace` alanları (hepsi opsiyonel, hepsi koddan):

| Alan | Anlamı |
|---|---|
| `target_det`, `target_track`, `target_link_m` | Rapor noktasında çekim anında bulunan araç ve noktaya uzaklığı |
| `target_dist_at_report_m` | Hedef araç rapor anında rapor noktasına ne kadar uzaktı |
| `target_moved_30m_before_report_m` | Rapordan önceki 30 dakikada yer değiştirmesi |
| `target_approach_30m_before_report_m` | Rapordan önceki 30 dakikada üsse yaklaşması (+ yaklaşıyor) |
| `target_moved_report_to_capture_m`, `target_approach_report_to_capture_m` | Rapor anından çekim anına hareketi |
| `claimed_duration_min`, `duration_covered_min`, `duration_max_move_m` | Metindeki süre, verinin kapsadığı kısmı, o sürede en büyük yer değiştirme |
| `followed_tracks[]` | Rapor anında noktada olan track'lerin çekim anındaki durumu: yerinde mi, karede mi, ne olarak tespit edildi |

**Boyut:** 40 görüntüde paket ortalama ~1,7K token. `trace` ortalama ~170, en fazla ~580 token ekliyor.

## 3. Prompt için önerilen paragraf

> **Rapor kontrollerinde `trace`:** Rapor belirli bir aracı anlatır; `target_track` o araçtır. Hareket iddialarını (duruyor / üsse geliyor / uzaklaşıyor) `target_*` alanlarıyla karşılaştır. Süre iddialarında `duration_covered_min < claimed_duration_min` ise en fazla KISMEN_DOGRULANDI verebilirsin. Hedef araç yoksa ve `followed_tracks` boşsa, rapor noktasında araç görünmüyor demektir. Kimlik ("bize bağlı", "ikmal", "dost devriye") hiçbir zaman doğrulanamaz; hareket tutuyorsa en fazla KISMEN_DOGRULANDI olur ve risk azaltılmaz.

## 4. Diğer notlar

1. **Arayüz:** Veri erişimi için `reports_for` ve `checks_for` fonksiyonlarına `D` parametresi eklendi: `reports_for(image_id, D)`, `checks_for(report, detections, capture_time, D)`.
2. **Bağlam raporları tekilleştirildi:** aynı metin birden çok kez geliyorsa en yenisi tutuluyor. 40 görüntüde toplam 262 → 103 rapor. Karar verilecek `reports` listesi aynen korunuyor; 40 görüntüde eski kodla birebir karşılaştırıldı.
3. **Validator ve hayalet raporlar:** `CELISIYOR` kanıt atfı istiyor, ama yokluğun bir kimliği yok. Öneri: bu durumda raporun kendi kimliği (`R039`) kanıt olarak kabul edilsin. Kural tabanı (`eval/baseline.py`) şu an böyle yapıyor.
4. **Örnek karar:** `example_decision.json`'da R001 "DOGRULANDI" görünüyor, ama örnek paket sahte sınıflarla üretilmiş. Gerçek tespitte T0182 **otomobil** ve 75 m içinde kamyon yok. Etiketli sette R001 "CELISIYOR" olarak duruyor.
5. **Değerlendirme:** `python -m eval.run_eval` kararları `cache/decisions/<image_id>.json` altında `Decision` JSON'u olarak arıyor. Farklı bir yol kullanılıyorsa `--decisions` ile verilebilir; varsayılan yol da istediğin yere çekilebilir. Kural tabanıyla karşılaştırma için `--baseline` kullanılır.
6. **Kişi 1 ve Kişi 3 için:** img_000860'taki kamyon (T0122) sadece 0,10 güvenle tespit ediliyor ve 1,65 km'de, ETA ~13 dakika. Mevcut eşiklerle (`YAKIN_YAKLASMA` <1,5 km, `YAKIN_VARIS` <10 dk) hiçbir sert bayrak tetiklenmiyor.

## 5. Bölge raporları: `ReportEv.zone_checks`

### Neden

Bölge adıyla yazılan 43 raporun 22'si bölgenin o anki durumu hakkında bir iddia ("ağır araç yok", "trafik normal", "olağandışı yok"). Şu an bu raporlar için LLM'in önünde sadece `ZoneSummary` var, yani **tek bir karedeki** tespit sayıları. Bu yetersiz:
- Kare ~150×85 m; bölge ise üsten 5 km dışarı uzanan bir koridor.
- Görüntü rapordan 120 dakikaya kadar sonra çekilmiş olabiliyor.
- Aynı rapor 1–3 görüntünün paketine giriyor ve her pakette farklı "kanıt" görüyor.

`zone_checks`, **bütün bölge** için ve **rapor anında** track'lerden ölçüm yapıyor. Rapor hangi pakete girerse girsin aynı gerçekleri taşıyor.

### Ekip kararları (uygulandı)

| # | Karar |
|---|---|
| 1 | "Olağandışı" = rapor anında bölgedeki bir track için sert bayrak koşulu (ARCHITECTURE §7). Hükmü LLM verir. |
| 2 | Pencere: rapor anı ±15 dk. |
| 3 | Ağır araç sınıfı track'e taşınır: bir çekim anında ≤3 m eşleşen, güveni ≥0,10 olan tespitten. 226 track'in 201'ine sınıf taşınıyor; T0122 (0,10) da dahil. |
| 4 | "Sabah devriyesi … bildirmedi" raporları aktarılan bir yokluk bildirimi; iddia değil bağlam. **`context_reports`'a taşındı** (`scope="bolge"`). Bu değişiklik `association.py`'de ve şu an etkin. |

### Değişiklik

```python
# dss/schemas.py
from dss.reports.zone_checks import ZoneChecks      # ya da modeller schemas.py'ye taşınır

class ReportEv(BaseModel):
    ...
    zone_checks: Optional[ZoneChecks] = None        # yalnızca bölge iddialarında (Kişi 4)
```

```python
# dss/evidence/builder.py — build_pack dışında, veri yüklenirken bir kez:
classes = track_classes(D, dets_by_image)           # 40 görüntünün tespitleri (Kişi 1 cache'i)
# rapor bölümünde:
for r in reports:
    if r.scope == "bolge" and parse_claim(r.text).category == "bolge_olumsuz":
        r.zone_checks = zone_checks_for(r, D, classes, dets_by_image)
```

Not: sınıf taşıma **40 görüntünün hepsinin** tespitlerine ihtiyaç duyuyor, `build_pack` ise sadece o görüntünün tespitlerini alıyor. Kişi 1'in cache'i (`cache/det_*.json`) hazır olana kadar `load_detections_file("data/image_box_and_reports/detections_all_ge0.10.json")` kullanılabilir.

`ZoneChecks` alanları: `zone`, `window`, `vehicles_seen`, `moving`, `unknown_class`, `heavy[]` ve `anomalies[]` (track, sınıf, ölçüm anı, üsse mesafe, hız, yaklaşma, bayraklar), `zone_images[]`, `radio_gap_reports[]`, `related_reports[]`.

**Boyut:** 40 görüntünün 22'sinde bölge iddiası var. Pakete ortalama ~100, en fazla ~380 token ekliyor.

### Veride ne çıktı?

- **"Ağır araç yok" (6):** 3'ünde bölgede ağır araç var. R017 ve R012'de T0174 (1,2–2,8 km, üsse yaklaşıyor), R092'de T0035 (1,7 km). Diğer 3'ünde yok.
- **"Kayda değer hareketlilik yok" (R042):** kamyon T0034 üsse 527 m, ETA <10 dk.
- **"Trafik normal" (7):** R099 ve R109'da hiçbir bayrak koşulu yok. Diğerlerinde aday var; hükmü LLM verir.
- **Yan bulgu:** T0035 aynı sabah üssün etrafında ~1,66 km yarıçapta dönüyor; Güneydoğu, Güneybatı ve Kuzeydoğu'da görünüyor.

### Prompt için önerilen paragraf

> **Bölge raporlarında `zone_checks`:** Bölge iddiası tüm bölge için, rapor anı ±15 dk içinde ölçülmüştür. `heavy` boş değilse "ağır araç yok" iddiası çürür. `anomalies` içinde YAKIN_VARIS, YAKIN_YAKLASMA ya da AGIR_ARAC_YAKIN varsa "olağandışı yok / trafik normal" iddiası çürür; tek başına UZUN_BEKLEME_YAKIN olağandışı sayılmaz. Hiçbir şey görülmemesi iddiayı tam doğrulamaz, çünkü park halindeki araçların kaydı olmayabilir: en fazla KISMEN_DOGRULANDI. `radio_gap_reports` doluysa o bölgedeki insan gözlemi zayıftır; drone verisine ağırlık ver.

### Etiketli set

R017 düzeltildi (tek kareye bakılıp "DOGRULANAMADI" denmişti, doğrusu "CELISIYOR"). R012, R042, R100 ve R099 eklendi. `python -m eval.run_eval --baseline` → 23 etiket.


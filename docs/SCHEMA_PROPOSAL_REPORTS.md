# Şema önerisi: `ReportChecks.trace` (Kişi 4 → Kişi 5)

**Durum:** Öneri. `dss/schemas.py`'ye henüz dokunulmadı. Kod hazır: `dss/reports/trace.py`.
**İstenen:** `ReportChecks`'e tek bir opsiyonel alan eklemek ve prompta kısa bir paragraf koymak.

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

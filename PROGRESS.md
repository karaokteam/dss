# İlerleme

Simgeler: ⬜ boşta · 🟨 devam ediyor · 🟩 bitti (test yeşil, merge edildi) · 🟥 takıldı

**Conflict'siz güncelleme:** Herkes sadece kendi aldığı step'in satırını değiştirir. Satırlar arasındaki boş
satırları silmeyin; git'in iki kişinin değişikliğini otomatik birleştirmesini bunlar sağlıyor.
Bir step'i almak için: `⬜` → `🟨` yap ve satırın sonuna `K<no>` yaz.

## Ekip

- K1 ·

- K2 ·

- K3 ·

- K4 ·

- K5 ·

- K6 ·

## Step durumu

### Step 0

- 🟩 Altyapı: şemalar, ayarlar, loaders, spatial, timeline, risk motoru, tool kaydı, fakes, UI iskeleti

- 🟩 Veri paketi geldi (`data/raw/`): 40 görüntü, 226 track / 5650 nokta, 137 rapor (98 official, 39 third_party, 08:35–15:15), 8 bölge. Loaders gerçek veriyle çalışıyor.

### VERI

- ⬜ VERI-1 · Veri kontrol scripti · K2

- ⬜ VERI-2 · Rapor havuzu incelemesi · K4

### DET

- ⬜ DET-1 · Model teslimi · K1

- ⬜ DET-2 · Tespit sarmalayıcı · K1

- ⬜ DET-3 · Tespit cache'i · K1

- ⬜ DET-4 · Güven eşiği kalibrasyonu · K1

### GEO

- ⬜ GEO-1 · Piksel → lat/lon · K2

- ⬜ GEO-2 · Tespitleri haritaya koy · K2

### TRK

- ⬜ TRK-1 · Tespit ↔ track eşleştirme · K2

- ⬜ TRK-2 · Hareket analizi · K3

### RAP

- ⬜ RAP-1 · Rapor sözlükleri · K4

- ⬜ RAP-2 · Regex iddia çıkarımı · K4

- ⬜ RAP-3 · İddia doğrulama · K4

### RSK

- ⬜ RSK-1 · Konum kuralları · K3

- ⬜ RSK-2 · Hareket kuralları · K3

- ⬜ RSK-3 · Rapor kuralları · K3

### LLM

- ⬜ LLM-1 · GLM istemcisi · K5

- ⬜ LLM-2 · Gerekçeli brief · K5

- ⬜ LLM-3 · LLM ile rapor çıkarımı · K5

- ⬜ LLM-4 · Sohbet tool'ları · K5

- ⬜ LLM-5 · Sohbet döngüsü · K5

### PIP

- ⬜ PIP-1 · 8 adımlı akış · K5

- ⬜ PIP-2 · Toplu tarama · K5

### UI

- ⬜ UI-1 · Harita bileşeni · K6

- ⬜ UI-2 · Değerlendir sekmesi · K6

- ⬜ UI-3 · Durum tablosu · K6

- ⬜ UI-4 · Sohbet sekmesi · K6

- ⬜ UI-5 · CLI · K6

### SUN

- ⬜ SUN-1 · Sunum iskeleti · K6

- ⬜ SUN-2 · Demo senaryosu · K6

- ⬜ SUN-3 · Yedek materyal · K6

### SON (kapı: STEPS.md §3)

- ⬜ SON-1 · Uçtan uca referans (`v0.5-e2e`) · K2

- ⬜ SON-2 · Risk kalibrasyonu · K3

- ⬜ SON-3 · Demo cache'i · K6

- ⬜ SON-4 · Prova + `demo-final` · K6

## Kararlar

OPEN_ISSUES'tan taşınan konular, ilgili alanın altına eklenir:

```markdown
#### OI-<ALAN>-<n> · Başlık — ✅ HH:MM · K?
**Karar:** ... · **Kanıt:** bulgu dosyası / PR · **Değişen:** config/... veya fonksiyon
```

### EKIP

#### OI-EKIP-3 · Veri paketi repoda mı dursun? — ✅ 2026-09-26
**Karar:** Repo private olduğu için paket `data/raw/`'a taşındı ve commit'lendi; herkes `git pull` ile alıyor. **Değişen:** `.gitignore` (data/raw artık dışlanmıyor), `config/paths.py` varsayılanı zaten `data/raw`.

### DET

### GEO

#### OI-GEO-1 · Görüntüler kuzeye hizalı mı? — ✅ 2026-09-26
**Karar:** Evet, doğrusal orantı kullanılacak (formül görev tanımında veriliyor). **Kanıt:** `data/raw/gorev_tanimi.pdf` + 40/40 görüntüde köşe eşitliği kontrol edildi. **Değişen:** GEO-1 (bilinear gerekmiyor). Not: görüntü boyutları farklı (960×540: 16, 1360×765: 19, 1920×1080: 5), bu yüzden `meta.width_px/height_px` kullanılmalı.

### TRK

#### OI-TRK-1 · Track zamanı ↔ çekim zamanı — ✅ 2026-09-26
**Karar:** Her track, ait olduğu görüntünün çekim anında biter; eşleştirmede `time == capture_time` kullanılır. **Kanıt:** görev tanımı + 226 track'in hepsinin son zamanı bir `capture_time`'a eşit. **Değişen:** `config/tracks.py` → `MATCH_TIME_TOLERANCE_MIN = 0`.

### RAP

### RSK

### LLM

#### OI-LLM-1 · GLM API bağlantı detayları — ✅ 2026-09-26
**Karar:** OpenAI-uyumlu gateway, tek model `glm-5.3-flash`, tool calling ve görüntü girdisi destekleniyor. Limitler: 60 istek/dk, aynı anda 4 istek, 15 $. `thinking` parametresi gönderilmez, `reasoning_effort` kullanılır. **Kanıt:** `data/raw/gorev_tanimi.pdf`. **Değişen:** `config/llm.py`, `.env.example` (sadece `GLM_API_KEY` gerekiyor, takıma ayrıca iletilecek).

### PIP

### UI

### SUN

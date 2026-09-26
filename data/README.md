# data/

| Klasör | İçerik | Git |
|---|---|---|
| `raw/` | Organizasyonun verdiği paket, **olduğu gibi** (düzenleme yok) | ✅ (repo private) |
| `samples/` | Case sunumundaki örnekler; testler bunları kullanır | ✅ |

Farklı bir yerde tutuyorsanız: `export DSS_DATA_DIR=/yol/paket`.

## Paket yapısı (`raw/`)

Paket repoda; kod varsayılan olarak buradan okur. Dosyalar düzenlenmez, türetilmiş her şey `cache/` ya da `exploration/` altına yazılır.

```
raw/
├── images/              40 drone görüntüsü (img_XXXXXX.jpg) — 960×540 / 1360×765 / 1920×1080
├── image_meta.json      {image_id: {width_px, height_px, capture_time "HH:MM", corner_coordinates{top_left,...: [lat,lon]}}}
├── zones.json           {base: {name, lat, lon}, zones: [{name, center: [lat,lon]}]}
├── tracks.csv           track_id,time,lat,lon — her track son 2 saat, 5 dk adım
├── field_reports.json   [{time, source: official|third_party, text}] — 137 rapor
└── gorev_tanimi.pdf     Aşama 2 görev tanımı + GLM API rehberi
```

Önemli (case brief):
- Track'ler ve raporlar **tek havuz**; hangi görüntüyle ilgili oldukları verilmez → bağlam `capture_time` + köşe koordinatlarıyla kurulur.
- **Raporların tamamı doğru değil**: kasıtlı/yanlışlıkla hatalı veya konu dışı olabilir. Önce kendi tespit + hareket verimize güveniriz.
- 200 px² altı araçlar etiket dışı.

## Kontrol
1. `python -m scripts.check_data` (VERI-1)
2. Bulguları `exploration/findings/` altına yaz, varsayım kırılıyorsa `OPEN_ISSUES.md`.

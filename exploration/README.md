# exploration/ — inceleme alanı

Gelen veriyi, model çıktılarını ve rapor metinlerini **serbestçe** incelemek için.
Buradaki kod `agent/`'ten import edebilir ama `agent/` buradan asla import etmez.

- `notebooks/NN_K<no>_konu.ipynb` — ör. `03_K2_track_endtimes.ipynb`. Commit'ten önce çıktıları temizle.
- `findings/YYYYMMDD_K<no>_konu.md` — bulgu notu (`_TEMPLATE.md`'yi kopyala).
- Branch: `exp/K<no>-<konu>` — sadece bu klasör değişir.

Akış: **bulgu → karar gerekiyorsa `OPEN_ISSUES.md` (OI-xx) → karar verilince `PROGRESS.md` + koda (ilgili `step/` veya `fix/` branch).**

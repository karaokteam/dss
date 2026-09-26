# Birlikte Çalışma — Git, Branch, PR, Conflict Önleme

6 kişi, tek repo (`karaokteam/dss`), yaklaşık 1 günlük süre. Hedef: **`main` her an demo edilebilir olsun ve
conflict'lerle neredeyse hiç uğraşmayalım.**

## 1. İlk kurulum (herkes bir kez)

```bash
git clone https://github.com/karaokteam/dss.git && cd dss
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # .env asla commit'lenmez

# Ortak hesap kullanılsa bile commit'lerde kimin yaptığı görünsün:
git config user.name  "Ad Soyad (K<no>)"
git config user.email "kendi@mailin"
git config pull.rebase true               # pull her zaman rebase ile
```

## 2. Conflict'i baştan önleyen düzen

Repo, iki kişinin aynı satırlara dokunmayacağı şekilde bölündü:

| Önlem | Nasıl |
|---|---|
| **Dosya başına tek sahip** | Her dosyanın başında sahibi olan step ID'si yazıyor. [STEPS.md](STEPS.md)'de her step'in "Yazılacak dosyalar" listesi var. Başkasının dosyasına dokunman gerekiyorsa önce ona sor. |
| **Paylaşılan dosyada bölümler** | `config/tracks.py`, `config/risk.py`, `pipeline.py`: her step kendi ID'siyle başlayan bölüme yazar. Bölümler boş satırla ayrıldığı için git bunları otomatik birleştirir. |
| **Otomatik kayıt** | Risk kuralları (`@rule`) ve sohbet tool'ları (`@tool`) bulundukları klasörden otomatik yüklenir. Listeye ekleme yapmak gerekmez, çünkü ortak liste yok. |
| **Şemalar ve ayarlar paket halinde** | `agent/schemas/` ve `agent/config/` alan başına dosyalara bölündü. `__init__.py` her şeyi toplu aktardığı için yeni sınıf ya da sabit eklerken `__init__`'e dokunulmaz. |
| **Sahte veri** | `agent/fakes.py` sayesinde kimse başkasının kodunu beklemez, başkasının dosyasına "geçici" kod da eklemez. |
| **Tek biçim** | `ruff format .` (ayarı `pyproject.toml`'da). Biçim farkından conflict çıkmaz. |
| **Satır sonları** | `.gitattributes` → herkeste LF. Windows/Mac karışık ekipte bütün dosyanın "değişmiş" görünmesi engellenir. |
| **Liste dosyaları** | `requirements.txt` ve `.gitignore` için `merge=union`: iki kişi aynı anda satır eklerse ikisi de korunur. |
| **Kayıt dosyaları** | `PROGRESS.md` ve `OPEN_ISSUES.md` alan bölümlerine ayrıldı, satırlar arasında boş satır var. Herkes sadece kendi satırını değiştirir. |
| **Notebook'lar** | Kişiye özel (`NN_K<no>_konu.ipynb`). Başkasının notebook'u düzenlenmez; commit'ten önce çıktılar temizlenir. |

## 3. Branch isimlendirme

```
step/<STEP-ID>-<kısa-ad>        ← normal iş, ör. step/GEO-1-projection
fix/<STEP-ID>-<kısa-ad>         ← merge edilmiş bir step'te hata, ör. fix/TRK-1-tolerance
exp/<K-no>-<konu>               ← sadece exploration/ değişir, ör. exp/K2-track-endtimes
docs/<konu>                     ← sadece .md dosyaları
chore/<konu>                    ← requirements, pyproject, CI
```

Bir branch = bir step. Step büyükse iki PR'a bölebilirsin (`step/RAP-2-coords`, `step/RAP-2-intent`).

## 4. Günlük akış

```bash
git switch main && git pull
git switch -c step/GEO-1-projection
# ... çalış, küçük commit'ler ...
git fetch origin && git rebase origin/main   # günde birkaç kez; conflict küçükken çözülür
ruff format . && ruff check . && pytest -q   # push'tan önce
git push -u origin step/GEO-1-projection     # rebase sonrası: git push --force-with-lease
# GitHub'da PR aç → şablonu doldur
```

- Branch ömrü **en fazla birkaç saat**. Uzarsa böl.
- `main`'e doğrudan push yok. Acil demo düzeltmesi istisna, o durumda ekibe yazarak yapılır.
- `git add -A` yerine dosya bazında ekle: `git add agent/geo/projection.py tests/test_projection.py`.

## 5. Ortak dosyalar (Step 0)

`agent/schemas/*`, `agent/config/paths.py`, `agent/loaders.py`, `agent/fakes.py`, `agent/geo/spatial.py`,
`agent/tracks/timeline.py`, `agent/risk/registry.py`, `agent/risk/scoring.py`, `agent/chat/tools/registry.py`, `app.py`,
`requirements.txt`, `pyproject.toml`

| Değişiklik türü | Kural |
|---|---|
| Yeni şema alanı (varsayılan değerli), yeni sınıf, yeni `fakes` fonksiyonu, yeni bağımlılık | Serbest. Küçük ayrı PR, başlıkta `[SCHEMA]` / `[CORE]`, ekip kanalına tek satır bilgi. |
| Mevcut bir alanı/imzayı değiştirmek veya silmek | Önce `OPEN_ISSUES.md`'ye yaz, etkilenen step sahipleri onaylasın, sonra PR. |
| Merge sonrası | "main'i çekin" diye haber ver. |

## 6. Commit mesajı

```
<STEP-ID>: <ne yapıldı — kısa>
```
Örnekler: `GEO-1: köşe koordinatlarından lat/lon enterpolasyonu` · `TRK-1: zaman toleransı dakika bazlı`
· `SON-2: HIGH eşiği 45→50 (scan_all dağılımı)` · `[SCHEMA] MotionProfile'a max_speed_mps eklendi`

## 7. Pull Request

- Şablon otomatik gelir (`.github/pull_request_template.md`).
- **Merge yöntemi:** *Squash and merge*.
- **Onay:** en az 1 kişi göz atar. Tek ortak hesap kullanıyorsak GitHub'da onay verilemez; bu durumda gözden geçiren kişi PR'a
  `✅ K<no>` yorumu yazar ve sonra merge edilir (OI-EKIP-1).
- Kırmızı test varken merge yapılmaz. Yazılmamış step'lerin testleri `skip` durumunda kalır; step sahibi skip satırını kendi PR'ında siler.

## 8. Kayıt ve bilgilendirme

| Durum | Nereye |
|---|---|
| Step'e başladım / bitirdim | `PROGRESS.md` → kendi step satırı (⬜ → 🟨 → 🟩), PR içinde |
| Karar gerektiren belirsizlik | `OPEN_ISSUES.md` → kendi alan bölümünün sonuna yeni `OI-<ALAN>-<n>` |
| Karar verildi | `OPEN_ISSUES.md`'den sil → `PROGRESS.md` "Kararlar" altındaki kendi alan bölümüne |
| Veri bulgusu | `exploration/findings/YYYYMMDD_K<no>_konu.md` |
| Ortak dosya değişti | PR başlığında `[SCHEMA]` / `[CORE]` + ekip kanalına mesaj |

## 9. Etiketler ve kod dondurma

- `v0.1-skeleton` (Step 0) · `v0.5-e2e` (SON-1) · `demo-final` (SON-4)
- Teslimden önce **kod dondurma**: yalnızca `fix/` ve `docs/` merge edilir. Saati OI-EKIP-2'de belirlenecek.

```bash
git tag -a v0.5-e2e -m "img_000860 uçtan uca" && git push origin v0.5-e2e
```

## 10. Conflict çıkarsa

```bash
git fetch origin && git rebase origin/main
# conflict'li dosyayı aç → iki tarafı da koruyarak düzelt
git add <dosya> && git rebase --continue
pytest -q && git push --force-with-lease
```
Başkasının dosyasında conflict çıktıysa kendi tarafını dayatma; o dosyanın sahibiyle birlikte çöz.

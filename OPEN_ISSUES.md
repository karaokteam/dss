# Açık Konular

Karar bekleyen konular burada. **Karar verilince konu buradan silinir ve kararıyla birlikte
[PROGRESS.md](PROGRESS.md) → "Kararlar" bölümüne taşınır.**

**Conflict'siz ekleme:** Konuyu kendi alanının bölümünün **sonuna** ekle. Numara `OI-<ALAN>-<sıradaki>` olsun;
numaralar alan içinde arttığı için iki kişi aynı numarayı almaz. Konular arasında boş satır bırak.

```markdown
### OI-<ALAN>-<n> · Başlık
- **Sahip:** step ID / K? · **Etkilediği step'ler:** ...
- **Soru:** ...
- **Varsayılan (karar verilene kadar):** ...
- **Nasıl çözülür:** veriye bakarak / organizasyona sorarak / ekip kararıyla
```

Karar bekleyen hiçbir konu işi durdurmaz: herkes **varsayılanla** devam eder, karar verilince sadece
`config/` değerleri ya da tek bir fonksiyon değişir.

---

## EKIP

### OI-EKIP-1 · GitHub hesap modeli
- **Sahip:** K6 · **Etkilediği:** CONTRIBUTING
- **Soru:** Herkes aynı hesapla mı push'layacak, yoksa `karaokteam` altında collaborator olarak mı?
- **Varsayılan:** Commit yazarını `git config user.name` ile ayırıyoruz, PR onayı yorumla veriliyor. Collaborator olursa `main` için "require PR" açılmalı.

### OI-EKIP-2 · Teslim formatı ve saatleri
- **Sahip:** K6 · **Etkilediği:** SON-4, SUN-*
- **Soru:** Kod teslimi repo linki mi yoksa zip mi? Sunum dosyasının formatı ne? Mentor oturumu ve jüri saatleri ne zaman? → Kod dondurma saati buna göre belirlenecek.

## DET

### OI-DET-1 · Agent görüntülerinde tespit eşiği
- **Sahip:** DET-4 · **Etkilediği:** tüm bulgular
- **Soru:** Agent görüntüleri 960×540; Kaggle verisiyle çözünürlük ya da irtifa farkı var mı? Kaggle'da düşük confidence zarar vermiyordu, burada yanlış alarm demek.
- **Varsayılan:** `DETECTION_CONF = 0.35`.

### OI-DET-2 · Model dosyası ve Kaggle notebook'u
- **Sahip:** DET-1 · **Etkilediği:** DET-2
- **Soru:** `best.pt` ekibe nasıl dağıtılacak (Drive, USB, GitHub Release)? Final notebook repoda tutulacak mı?
- **Varsayılan:** Release asset olarak eklenir, notebook `kaggle/notebooks/` altına.

## GEO

## TRK

### OI-TRK-2 · Eşleştirme mesafe sınırı
- **Sahip:** TRK-1 · **Etkilediği:** TRK-1
- **Soru:** Görev tanımı "birkaç metre sapma, makul bir sınır içinde en yakın nokta" diyor (örnekte 2,5 m). Sınır kaç metre olsun?
- **Varsayılan:** Sadece mesafe, `MATCH_MAX_DIST_M = 15`. Gerçek veride eşleşme mesafelerinin dağılımına bakılarak ayarlanacak.

## RAP

### OI-RAP-1 · Rapor güvenilirliği
- **Sahip:** RAP-3 / RSK-3 · **Etkilediği:** RAP-3, RSK-3, LLM-2
- **Soru:** `official` ve `third_party` raporlar farklı ağırlık alsın mı? Konu dışı rapor nasıl ayıklanır?
- **Varsayılan:** Kaynak türü puanı değiştirmez, sadece brief'te belirtilir. Güven verici iddialar hiçbir zaman puan düşürmez.

## RSK

### OI-RSK-1 · Risk seviyeleri ve ETA tanımı
- **Sahip:** SON-2 / TRK-2 · **Etkilediği:** RSK-*, SON-2
- **Soru:** Seviye sınırları ne olsun? ETA kuş uçuşu mu hesaplansın (yol verisi yok)? "Yaklaşıyor" ne demek?
- **Varsayılan:** 4 seviye (`config/risk.py`). ETA kuş uçuşu. Son 30 dk'da üsse mesafe azalıyorsa "yaklaşıyor".

### OI-RSK-2 · Eşleşmeyen tespit / görüntüde olmayan track
- **Sahip:** RSK-2 / TRK-1 · **Etkilediği:** RSK-2, LLM-2
- **Soru:** Görev tanımına göre park halindeki araçların kaydı olmayabilir, kaydı olan araç da görüntü dışında kalmış olabilir. Bunlar nasıl puanlanır ve brief'te nasıl anlatılır?
- **Varsayılan:** Eşleşmeyen tespit "muhtemelen park halinde" sayılır; sadece konum kuralları uygulanır. Görüntü dışındaki track'ler bu görüntünün bulgusu sayılmaz.

## LLM

### OI-LLM-2 · 15 $ bütçe ve düşünme seviyesi
- **Sahip:** LLM-1 · **Etkilediği:** LLM-2, LLM-3, LLM-5
- **Soru:** Tek model var (glm-5.3-flash). Hangi çağrıda `reasoning_effort` low, hangisinde high olsun?
- **Varsayılan:** Rapor çıkarımı `low` ile bir kez yapılıp cache'lenir. Brief ve sohbet `high`. Tüm yanıtlar cache'lenir, sohbet en fazla 10 tur.

### OI-LLM-3 · Görüntüyü LLM'e de göstermek
- **Sahip:** LLM-2 · **Etkilediği:** LLM-2, LLM-4
- **Soru:** Model görüntü okuyabiliyor (960×540 ≈ 700 token). Brief'e ya da sohbete nitel bir "ikinci göz" eklensin mi (ör. "kasada yük görünüyor mu")? İlke 1 gereği sayı ve seviye yine Python'dan gelir.
- **Varsayılan:** Hayır. Zaman kalırsa LLM-4'e opsiyonel bir `describe_image` tool'u eklenir.

## PIP

## UI

## SUN

### OI-SUN-1 · Demo güvenilirliği
- **Sahip:** SON-3 · **Etkilediği:** SON-3, SUN-3
- **Soru:** Demo'da model ve LLM canlı mı çalışacak, yoksa cache'ten mi? Demo cache'i repoya konulacak mı?
- **Varsayılan:** Tespit cache'ten, LLM canlı. LLM düşerse şablon brief kullanılır. Demo görüntülerinin cache'i `cache/`'e konur, repoya konmaz.

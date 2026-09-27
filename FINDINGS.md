# FINDINGS — Karar Bekleyen Noktalar ve Karar Günlüğü

> Motor geliştirilirken çıkan, senin onayını bekleyen noktalar (A) ve verilmiş kararlar (B).
> Veri bulgularının sunum odaklı anlatımı: [CASE.md](CASE.md) §3.
> Durum: 🟡 karar bekliyor · ✅ karar verildi

---

## A. Karar bekleyen noktalar

### A1 🟡 Tutarlı yaklaşan otomobiller "yüksek" mi olmalı?
- **Durum:** T0020, T0184 ve T0091 üsse 1,6–1,9 km'ye kadar her hareketinde yaklaşan otomobiller; skorları 55–60 (**yüksek**). Aynı davranışı gösteren kamyon T0122 ise 75 (**kritik**).
- **Seçenekler:** (a) Olduğu gibi kalsın: tip farkı zaten +15. (b) Otomobillerde `consistent_approach` ağırlığı düşürülsün, "orta" seviyeye insinler.
- **Öneri:** (a). Otomobil de keşif veya sızma aracı olabilir; tip farkı zaten sıralamayı koruyor.

### A2 🟡 Duran kamyon grupları
- **Durum:** img_005368'de 2 saattir üsse 2,7 km mesafede birlikte bekleyen iki kamyon var (T0019, T0117; `co_movement`: `waiting_together`). Skorları 65 (**yüksek**). Puanın 20'si çelişen "dost otomobil" raporundan geliyor.
- **Soru:** Grup ağırlığı (+10) ve rapor çelişkisi (+10, dost iddiası +10) yeterli mi, fazla mı?
- **Öneri:** Kalsın. Agent gerekçesiyle skoru aşağı veya yukarı çekebilir.

### A3 🟡 "Son 1 saatte yaklaştı" etiketinin ağırlığı
- **Durum:** 226 track'in 121'i bu etiketi alıyor, çünkü görüntüler track başlangıçlarına göre üsse daha yakın. `approaching` (+10) ve `fast_approach` (+10) birlikte 1,6–1,9 km'deki birçok otomobili 40 puanla **orta** seviyeye çıkarıyor. Toplamda 77 orta seviye araç var.
- **Seçenekler:** (a) Olduğu gibi kalsın. (b) Tutarlı yaklaşma yoksa `approaching` 5'e insin.
- **Öneri:** (a). Orta seviye "izlenmeli" anlamına geliyor. Agent bağlama bakarak seviye düşürebilir.

### A4 ✅ Aynı görüntüdeki koordineli hareket → sinyal DEĞİL (kanıt dosyasına eklenmedi)
- Kanıt dosyasında denendi: 24 görüntü içi çiftte "ayrı yerlerden ≥4 kez aynı anda aynı yöne hareket" bulundu.
  Ancak 580 çiftte tesadüfen ~%5, yani **~29 çift beklenir**. Bu yüzden bulgu tesadüften ayırt edilemiyor.
- **Karar:** Görüntü içi `coordinated_arrival` anomalisi yok. Yalnızca güçlü `convoy` kontrolü var (2 saat boyunca ≤150 m arayla birlikte hareket; veride 0).
  `co_movement` tool'u hipotez sınaması için kalıyor; çıktısında çoklu karşılaştırma uyarısı var.
- T0028–T0001 (img_003464) bulgusu da bu nedenle tek başına anlamlı değil.

### A5 ✅ Genel tablo kanıt dosyasına eklendi
- `global_context`: çekim anında (yalnızca o ana kadarki kayıtla) bölge bazında üsse tutarlı yaklaşan araç sayısı, ağır araç sayısı, en yakın mesafe.

### A6 ✅ Kaçırılmış tespit adayları eklendi + görsel bulgu
- Tespitsiz 4 track'in hepsinde ≤ 1 m içinde eşik altı ham tahmin var (car 0,04–0,09). Bu tahminler kanıt dosyasına `candidates` olarak eklendi; kutuları vision kırpmasında kullanılıyor.
- **Görsel teyit (inspect_image):** T0057 bir reklam panosunun üst kenarında, T0188 bir ağacın altında kalıyor (örtülü). T0046 ağaç altında yarı görünür beyaz otomobil, T0027 açıkta beyaz otomobil (düşük netlik).
  Yani model bu araçları büyük ölçüde **örtülme** yüzünden kaçırmış; track aracın orada olduğunu söylüyor.

### A7 🟡 Rapor kaynağının ağırlığı
- **Bulgu:** Koordinatlı raporlarda **official raporların %57'si (28/49) çelişkili**, third_party raporlarda ise **%39 (9/23)**. Çelişkilerin çoğunu official kaynaklı dost/ikmal iddiaları oluşturuyor.
- **Karar:** Kaynak türü (official / third_party) güvenilirlik göstergesi olarak kullanılmasın. Raporlar yalnızca gözlemle doğrulandığı ölçüde ağırlık alsın. Kaynak bilgisi agent'a gösterilir ama puanı etkilemez.
- **Öneri:** Kaynak puanı etkilemesin (şu anki durum).

### A8 🟡 Anlatılan araç bulunamayan iddialar
- **Şu anki politika:** Dost/ikmal iddiasının anlattığı araç yoksa → `contradicted`. Diğer iddia tiplerinde → `unverifiable` + `claim_without_vehicle` anomalisi (12 rapor).
- **Gerekçe:** Park halindeki bir araç görüntü dışında kalmış olabilir, bu yüzden "araç yok" kesin çelişki sayılmıyor. Dost iddiası ise risk düşürmeye yönelik olduğu için ispat yükü raporda.
- **Öneri:** Kalsın.

### A9 🟡 Kaydın başından beri durağan olan araçlarda süre iddiası
- **Durum:** R053 (08:50) "bir saatten uzun süredir" diyor, ama T0045'in kaydı 08:15'te başlıyor. Yani yalnızca 35 dakikalık bir alt sınır görülebiliyor. Kaydın tamamında durağan olduğu için iddia `verified` sayılıyor ve gerekçede bu açıkça yazıyor.
- **Öneri:** Kalsın.

---

### A10 ✅ Maliyet takibi: header maliyeti gerçeğin ~1/3'ü
- Gateway'in yanıt başına bildirdiği `x-litellm-response-cost`, gerçek harcamanın ~3 katı düşük çıkıyor: header'lardan toplanan tutar 0,069 USD, gateway'in toplam harcaması aynı sürede +0,21 USD.
- Bütçe freni zaten gerçek harcamaya (`x-litellm-key-spend` / `/key/info`) bakıyor, koruma doğru çalışıyor. CLI'daki çalıştırma maliyeti artık gateway harcama farkından hesaplanıyor.
- **Bütçe durumu (27.09):** harcanan ~0,23 USD / 15 USD. 40 görüntünün agent değerlendirmesi için tahmin ~0,3–0,6 USD.
- **Koruma:** görüntü başına en fazla 8 LLM çağrısı ve 6 tool çağrısı; bütçe freni 13 USD; tüm yanıtlar önbellekli (tekrar çalıştırma ücretsiz, prompt değişmedikçe).

## B. Karar günlüğü

| Tarih | Karar | Gerekçe |
|---|---|---|
| 2026-09-26 | ✅ Hibrit mimari: deterministik kanıt hattı + tool kullanan agent | Zorunlu kanıtın agent'ın insiyatifine kalmaması; esneklik tool registry'de |
| 2026-09-26 | ✅ Backend Flask, UI React (motordan sonra planlanacak) | — |
| 2026-09-27 | ✅ Yol ağı kullanılmayacak; tüm metrikler kuş uçuşu | Track'ler 5 dk'lık ve sıçramalı olduğu için yola eşleme belirsiz; tehdit sinyali (radyal hız) yoldan bağımsız |
| 2026-09-27 | ✅ Piksel → koordinat, PDF'teki doğrusal oranlama (açı/projeksiyon yok) | 323 tespitte fark < 0,07 m |
| 2026-09-27 | ✅ Prompt'lar koddan ayrı `backend/prompts/*.md`, sürüm hash'i ile | Kod değişmeden iyileştirme; sunumda gösterilebilir |
| 2026-09-27 | ✅ "Yakınsama" sinyali kaldırıldı → "tutarlı yaklaşma" | 184/226 track son 5 dakikada varmış; her hareketinde yaklaşan yalnızca 7 track var |
| 2026-09-27 | ✅ ETA yalnızca hareket halindeki araçlar için | Uzun süredir duran araçta ortalama hız yanıltıcı |
| 2026-09-27 | ✅ Rapor parser: LLM + kural çapraz kontrolü (varsayılan LLM) | Kurallar bu veride 32/32 kalıbı kapsıyor, LLM farklı günün verisine genellenir; 137/137 uyum |
| 2026-09-27 | ✅ `quiet` durumu `normal` ile birleştirildi | Aynı anlam; LLM ve kurallar ayırt edemiyordu |
| 2026-09-27 | ✅ Park halindeki özneler için güven ≥ 0,30 | Düşük güvenli track'siz tespitler yanlış pozitif olabilir |
| 2026-09-27 | ✅ Risk ağırlıkları: `consistent_approach` 15 → 20, `report_contradiction` 15 → 10 | Fiziksel tehdit rapor çelişkisinden ağır basmalı; çelişki tek başına kritik üretmemeli |
| 2026-09-27 | ✅ Tool ilkesi: tool yalnızca belirsizlik soruşturması içindir | Deterministik veri kanıt dosyasında; tool'lar: `vehicles_in_area`, `co_movement`, `inspect_image` (Step 8) |
| 2026-09-27 | ✅ `co_movement` "buluştular" eşiği ≥ 4 eşzamanlı hareket, çıktıda tesadüf oranı | Rastgele çiftlerde ≥2 %43, ≥3 %19–24, ≥4 %2–5 |
| 2026-09-27 | ✅ Görüntü içi koordineli varış anomalisi eklenmedi (A4) | 24 bulgu vs ~29 tesadüfi beklenti |
| 2026-09-27 | ✅ Vision tool: hedef kırmızıyla işaretli, büyütülmüş kırpma; `occluded` alanı | Görüntülerin bir kısmı eğik açılı; kaçırılan araçlar pano/ağaç altında |
| 2026-09-27 | ✅ Agent döngüsü: son iterasyon her zaman cevaba ayrılır; tool üst sınırı 12 → 6 | Testte tool hakkı iterasyonlardan önce bitmediği için model cevap veremeden yedeğe düşüyordu |
| 2026-09-27 | ✅ Agent çıktısı: yalnızca önemli araçlar yazılır, gerisi temel seviyeyle eklenir; sapma gerekçe ister; kanıt kimlikleri veride doğrulanır | Kısa çıktı + denetlenebilirlik |

---

## C0 ✅ Prompt düzeltmesinin etkisi (run1 → run2, 40 görüntü)
| | run1 | run2 |
|---|---|---|
| Agent'ın temel seviyeyi değiştirdiği araç | 40 (38 yükseltme) | **11 (8 yükseltme)** |
| "Koordinasyon" dikkat maddesi olan görüntü | 22 | **8** |
| Görüntü genel riski | 1 kritik / 19 yüksek / 15 orta / 5 düşük | 2 kritik / 7 yüksek / 25 orta / 6 düşük |
| Yedek sonuç | 0 | 0 (koruma olumsuz cümleleri de yakalıyordu; düzeltildi, 2 görüntü yeniden çalıştırıldı) |
Eklenenler: prompt kuralları 5–8 + deterministik koruma ("tutarlı yaklaşma" yalnızca işaretli araçlar için; olumsuz ifadeler hariç).
Maliyet: run2 0,165 USD; toplam harcama ~0,53 / 15 USD. Önceki sonuçlar `outputs/assessments_run1/`.

## C. Step 9 elle inceleme notları (toplu çalıştırma bitince prompt ayarı)
- **img_000860:** Agent, T0192–T0032 çiftini `chance_rate` 0,053'e dayanarak **yüksek** seviyeli "koordineli buluşma şüphesi" yaptı; tool çıktısındaki çoklu karşılaştırma uyarısını dikkate almadı. Ayrıca "6 araç tutarlı yaklaşarak" demiş, oysa kanıt dosyasında tutarlı yaklaşan yalnızca T0122 ve T0020 var. → Prompt: tesadüf oranı tek başına dikkat maddesi olamaz; "tutarlı yaklaşma" ifadesi yalnızca `TUTARLI YAKLAŞMA` işaretli araçlar için kullanılabilir.
- **img_000267 (Step 8 denemesi):** T0226 için "tutarlı yaklaşma" demiş, oysa aracın 8 hareketinin 2'si uzaklaşan (aynı sorun).
- **Olumlu:** T0122'nin tespit güveni yalnızca 0,10; agent vision ile aracın gerçekten yüklü bir kamyon olduğunu teyit etti ve seviyeyi kritik tuttu.

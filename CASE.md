# Aşama 2 — Case Analizi

> Sunum için referans doküman. Görev tanımı (`stage2/gorev_tanimi.pdf`) ve verinin kendisi incelenerek yazıldı.
> Buradaki sayılar gerçek veriden hesaplanmıştır (aksi belirtilmedikçe).

---

## 1. Görev tek cümlede

Bir üssü koruyoruz. Çevredeki bölgeler gün boyu drone'la izlendi. **Her drone görüntüsü için** hangi durumların
dikkat gerektirdiğini, **neden** gerektirdiğini ve **hangi veriye dayandığını** açıklayan bir LLM agent geliştiriyoruz.

## 2. Elimizdeki veri

| Kaynak | İçerik | Gözlem |
|---|---|---|
| `images/` + `image_meta.json` | 40 kuşbakışı görüntü, çekim saati, 4 köşe koordinatı | 10:10–15:50 arası, 3 çözünürlük (960×540, 1360×765, 1920×1080). Görüntüler küçük alanları kapsıyor (~100–350 m), üsse 1,6–5,4 km uzakta. |
| `zones.json` | Merkez Üs + 8 bölge merkezi | Bölgeler üssün etrafında halka gibi dizilmiş (K, KD, D, GD, G, GB, B, KB). |
| `tracks.csv` | 226 hareket kaydı × 25 nokta (2 saat, 5 dk adım) | **Her track tam olarak bir görüntünün çekim saatinde bitiyor.** Görüntü başına 3–10 track. |
| `field_reports.json` | 137 serbest metin rapor (98 official, 39 third_party) | 08:35–15:15 arası. Doğru, yanlış ve ilgisiz raporlar karışık; hiçbiri işaretlenmemiş. |
| `detections_output/.../detections.json` | 1. gün modelimizin çıktısı: 323 tespit (250 car, 40 truck, 29 van, 4 bus) | Her tespit için bbox, güven skoru, merkez lat/lon ve alternatif etiketler hazır. |

## 3. Kilit bulgular

### 3.1 Analiz birimi görüntü
Görev, "verilen drone görüntüsünü değerlendir" diyor. Hareket kayıtları da görüntülere göre kurgulanmış: her track'in son noktası,
ait olduğu görüntünün çekim anındaki konumu. Dolayısıyla sistem **rapordan değil görüntüden başlar**.

### 3.2 Tespit ↔ track eşleşmesi çok temiz
Tespit merkezleri ile çekim saatindeki track noktaları arasındaki mesafe çoğunlukla **1 m'nin altında**.

| Durum | Sayı | Yorum |
|---|---|---|
| Birebir eşleşen (≤5 m) | 202 tespit ↔ 202 track | Kapı mesafesini (gate) 3 m'den 15 m'ye çıkarmak sonucu neredeyse değiştirmiyor. |
| Track'i olmayan tespit | 121 | Medyan güven 0,28, yani çoğu düşük güvenli. Güveni ≥0,5 olan 36 tanesi büyük ihtimalle **park halindeki araç**. |
| Tespiti olmayan track | 24 | 20'si çekim anında **görüntü dışında** (PDF bunun normal olduğunu söylüyor). **4'ü görüntü içinde**, yani olası kaçırılmış tespit. |

> 15 m içinde 267 tespit bir track'e yakın, ancak birebir eşleşme 202'de kalıyor. Yan yana araçlar olduğu için
> **birebir atama (Hungarian)** şart. En yakını seçmek aynı track'i birden fazla araca bağlar.

### 3.3 Raporlar görüntülere bağlanacak şekilde tasarlanmış
- **72 koordinatlı rapor**un hepsi bir görüntünün alanına **4–133 m** yakınlıkta ve o görüntüden **5–120 dk önce** yazılmış.
  Bu, track'in 2 saatlik penceresine denk geliyor. Yani rapor aracın **geçmişteki bir anını** anlatıyor.
  Raporu doğrulamanın en iyi yolu, **rapor saatinde track'in o koordinatta olup olmadığına** bakmak.
- **43 bölge adlı rapor** çoğunlukla genel bağlam: "trafik normal", "doğrulanamayan ihbar", "telsiz bağlantısı yok".
- **22 rapor** ne koordinat ne bölge içeriyor: hava durumu, lojistik konvoyu, tatbikat. Bunlar gürültü.

### 3.4 Rapor iddia tipleri

| İddia tipi | Örnek metin | Doğrulama yöntemi |
|---|---|---|
| Sayım | "5 kamyonun durduğu bildirildi" | Rapor saatinde o yarıçaptaki track sayısı ve görüntüdeki tespit sayısı |
| Durağanlık | "bir saatten uzun süredir yerinden ayrılmadı" | Track'in rapordan önceki 60 dakikadaki yer değiştirmesi |
| Hareket | "üsse doğru ilerleyen", "bölgeden uzaklaşıyor", "transit geçiyor" | Üsse göre radyal hızın işareti ve yön |
| Kimlik / dost | "dost devriye unsurudur", "planlı ikmal aracıdır, kimlik teyidi yapılmıştır" | Tip, renk (kırpılmış görüntü + vision) ve hareket uyumu |
| Yoğunluk | "olağan trafik 4 araç civarıdır" | Gözlenen sayının bu normla karşılaştırılması |
| Bölge geneli | "Güneybatı Yolu'nda ağır araç yok" | O bölgedeki görüntülerde truck/bus tespiti |
| Gürültü | hava, konvoy, tatbikat | Karara etkisi yok, yalnızca bağlam |

### 3.5 Tuzaklar
Görev açıkça şunu söylüyor: *"Çelişki varsa raporu değil tespitinizi esas alın."* Veride bunu test eden örnekler var:

- **`img_003201` (14:55)**, aynı nokta için üç birbiriyle çelişen rapor:
  - 13:15 "1 ağır araç (kamyon/otobüs)"
  - 13:20 "otomobil uzun süredir hareketsiz"
  - 13:55 "üsse ilerleyen panelvan, planlı ikmal, kimlik teyitli"
- **Risk düşürücü iddialar**: "dost unsur", "planlı ikmal", "gün içinde dost unsurlar bulunacak".
  Bunlar doğrulanmadan riski düşüremez. Tespit veya track ile çelişiyorlarsa tam tersine **şüphe sinyalidir**.

### 3.6 Gerçek bir örnek: `img_000267` (10:15, Doğu Yolu, üsse ~3,6 km)
- `img_000267_003`: **truck** (güven 0,82) ↔ `T0045`, eşleşme mesafesi 0,1 m.
  Track, 2 saat boyunca en fazla ~25 m oynuyor, yani araç **yerinden ayrılmamış**.
- 08:50 official rapor: "39.92087N 32.89536E konumundaki kamyon bir saatten uzun süredir yerinden ayrılmadı." → **DOĞRULANDI**
- 08:45 official rapor: "39.9209N 32.8953E yakınında **2 kamyonun** durduğu bildirildi." → Görüntüde ve track'lerde yalnızca 1 kamyon var: **KISMEN ÇELİŞKİLİ**
- `T0134` (van) ve `T0226` (car) çekimden hemen önce birkaç km öteden bu noktaya gelmiş. Ancak bu tek başına sinyal değil: 226 track'in 184'ü son 5 dakikada bulunduğu noktaya varmış (bkz. §3.7).

### 3.7 Hareket düzeni
- Araçlar **bekle → sıçra → bekle** düzeninde hareket ediyor. Beklerken ardışık noktalar arası titreme **< 20 m**, gerçek hareket adımları **≥ 76 m** (çoğu 5 dakikada 1–3 km, en fazla ~2,8 km ≈ 9 m/s).
  Bu yüzden her 5 dakikalık adım 60 m eşiğiyle güvenle "hareket" veya "bekleme" diye ayrılır.
- **226 track'in 184'ü son 5 dakikada bulunduğu noktaya varmış.** Yani "yeni gelmiş olmak" veya "birkaç aracın aynı noktaya yakınsaması" bu veride olağan; tek başına sinyal değildir.
- Güçlü sinyal **tutarlı yaklaşma**: 2 saat boyunca **her** hareketi üsse yaklaştıran track sayısı yalnızca **7**.
  Örnek: `T0020` 2 saatte üsse 7,8 km'den 1,6 km'ye gelmiş ve 50 dakikadır orada bekliyor.
- Dağılım: 30 track hiç hareket etmemiş, 12'si her hareketinde uzaklaşmış, 177'si karışık hareket etmiş.
- Pencereler PDF örneğiyle aynı: **hız** son 30 dakikadan, **üsse uzaklık değişimi** son 60 dakikadan ölçülür.
  ETA yalnızca araç hâlâ hareket ediyorsa verilir; 30 dakikadan uzun süredir duran araç için ortalama hız yanıltıcıdır.

### 3.8 Raporların doğrulama sonuçları (Katman 1, LLM'siz)
**Rapor koordinatı, anlattığı aracın GÖRÜNTÜDEKİ konumudur** (5 ondalıklı koordinatların 31/35'i görüntüdeki bir araca ≤ 3 m; rapor saatindeki konuma yakın olan 0/35; görev tanımındaki örnek de böyle eşleştirir). Özne görüntüde aranır (tolerans: 5 hane ~3 m, 4 hane ~12 m; tip uyuşan tercih edilir); iddia ise aracın **rapordan önceki 30 dakikadaki** davranışıyla yargılanır. Rapordan sonra çekime kadar üsse yaklaşma ayrıca bayraklanır.

| Kalıp | Örnek | Sonuç |
|---|---|---|
| **Güven verici iddia, sonra yaklaşan araç** | R126 "hareketleri olağan" (12:35) → T0122 kamyonu o an duruyor, sonra üsse 4,3 km yaklaşıyor | `partial` + şüphe |
| **Dost iddiası, yaklaşan araç** | R113 "bize bağlı" → T0124 30 dk'da üsse 3,2 km yaklaşmış; R129 "planlı ikmal" → T0156 yaklaşıyor | `partial` + şüphe |
| **Ters yön** | R007 "üsse gelen dost otomobil" → T0131 rapordan önce 1,9 km uzaklaşıyor; R083 → T0226 1,1 km uzaklaşıyor | `contradicted` |
| **Sayı şişirme** | R018 "5 kamyon" → 1 (`contradicted`); R094 "2 kamyon" → 1, R101 "7 kamyon" → 5 (`partial`) | |
| **Kısmi kapsama** | R053 "bir saatten uzun süredir" → T0045 kaydın kapsadığı 35 dk boyunca durağan, kalanı veride yok | `partial` |
| **Bölge raporu çelişkisi** | R017 "Güney Kapısı'nda ağır araç yok" (10:20) → T0174 kamyonu; R042 "Kuzeybatı'da olağandışı yok" (15:00) → T0034 kamyonu üssün etrafında dönüyor | `contradicted` |
| **Yokluk** | R092 / R100 "ağır araç yok" → kayıtta yok; park halindeki araçların track'i olmayabilir | `partial` |

Özet: **dost/ikmal iddialarının 17/18'i üsse yaklaşan (rapordan önce ya da sonra) bir araca iliştirilmiş.** Kimlik veriden teyit edilemez; bu veride dost iddiaları **risk düşürücü değil, şüphe sinyali**. Tüm raporlar: 28 doğrulandı, 38 kısmen, 22 çelişkili, 49 doğrulanamaz.
Ekibin elle etiketlediği 23 raporla (`eval/gold_reports.json`, `python -m backend.cli eval`): **22/23 uyum**.

### 3.9 Temel risk sıralaması (kural tabanlı, agent öncesi)
- 327 araç (323 tespit + 4 tespitsiz track): **6 kritik, 20 yüksek, 68 orta, 233 düşük**.
- En üstte **T0122** (img_000860, 14:10, 85): 2 saatte her hareketi üsse yaklaştıran, 6 km'den 1,6 km'ye gelen **kamyon**; üstelik 12:35'te "hareketleri olağan" raporu bu araca iliştirilmiş.
- **Üssün etrafında dönen 5 araç** (70–85): T0043 (10:15–10:25, 630 m), T0158, T0172, T0198 otomobil ve T0034 kamyon (14:45–15:05, 527 m). Dönüş görüntüler arasında olur; yalnızca hareket kaydından bulunur.
- Ardından: T0095 / T0174 kamyonları, img_003464'teki kamyon grubu, tutarlı yaklaşan otomobiller T0020 / T0184 / T0091.
- Ağırlık ilkesi: fiziksel tehdit (dönme, yakınlık, tutarlı yaklaşma, ağır araç) raporlardan ağır basar; hiçbir rapor riski düşürmez.

### 3.10 Kaçırılan araçlar neden kaçırıldı?
Tespitsiz 4 track'in hepsinin tam konumunda modelin eşik altı (0,04–0,09) bir `car` tahmini var. Görsel teyitte T0057'nin bir reklam panosunun kenarında, T0188'in ise bir ağacın altında kaldığı görüldü; T0046 ağaç altında yarı görünür durumda.
Yani kaçırmaların nedeni büyük ölçüde **örtülme**. Tespit modelinin göremediği aracı hareket kaydı yakalıyor; füzyonun değeri burada ortaya çıkıyor.

## 4. Kanıt hiyerarşisi

```
1. Tespit (YOLO + koordinat)   → en güvenilir: "ne, nerede"
2. Hareket kaydı (track)       → "nasıl geldi, ne yapıyor"
3. Rapor (official > third_party) → yalnızca doğrulandığı ölçüde ağırlık alır
```

## 5. Değerlendirme mantığı: her araç için 5 soru

1. **Ne?** YOLO ile tip: car / van / truck / bus (+ alt etiketler, güven).
2. **Nerede?** Koordinat, üsse uzaklık, bölge.
3. **Ne yapıyor?** Track'ten: yaklaşıyor/uzaklaşıyor (radyal hız), hız, ETA, duruş süresi, dolaşma (tortuosity), ani değişim.
4. **Hakkında ne deniyor?** Rapor saatinde track'in rapordaki koordinata yakın olup olmadığı.
5. **Söylenen ile görülen tutuyor mu?** DOĞRULANDI / ÇELİŞKİLİ / DOĞRULANAMAZ.

### Risk boyutları

| Boyut | Riski artıran |
|---|---|
| Yakınlık | Üsse yakınlık |
| Yönelim | Üsse yaklaşma, kısa ETA |
| Tip | Truck / bus (ağır araç) |
| Davranış | Tutarlı yaklaşma (her hareket üsse doğru), üsse yakın uzun bekleme, dolaşma |
| Grup | Kümelenme, "olağan" sayının üstü |
| Rapor | Çelişki, özellikle doğrulanmamış dost/ikmal iddiası |

**Kural:** Dost iddiası riski **ancak doğrulanırsa** düşürür. Çelişirse riski artırır.

## 6. Mimari karar: hibrit

**Soru:** Raporları LLM'e verip hangi tool'u kullanacağına kendisi mi karar versin, yoksa kural bazlı mı yönlendirelim?

**Karar:** İkisinin birleşimi.

| Katman | Ne yapar | Neden |
|---|---|---|
| **1. Deterministik kanıt hattı** | Her görüntü için tespit → koordinat → track eşleştirme → kinematik → rapor bağlama → iddia doğrulama → temel risk skoru. Çıktısı bir "kanıt dosyası" (dossier). | Koordinat mı bölge mi ayrımı bir sınıflandırmadır; regex hatasız yapar. Zorunlu kanıtın agent'ın insiyatifine kalmaması gerekir, yoksa kaçırılan tehdit sessizce kaybolur. Sonuçlar tekrarlanabilir ve denetlenebilir olur. |
| **2. LLM agent + tool registry** | Kanıt dosyasını okur. Gerekirse tool çağırarak derinleşir (track geçmişi, yakın raporlar, görüntü kırpma + vision, bölge istatistiği). Son risk kararını ve gerekçesini yazar. | Esneklik burada: yeni bir durum için yeni tool eklemek yeterli. Belirsiz ve alışılmadık vakaları LLM çözer. |

**İlke:** Bilinmeyen bir durum hiçbir zaman sessizce düşmez. `unknown` / "belirsiz" olarak işaretlenir ve agent'a gider.

## 7. Farklı durumlar

| Durum | Davranış |
|---|---|
| Tespit var, track yok | Park halinde varsayılır. Konum ve tipe göre değerlendirilir, "hareket bilinmiyor" diye işaretlenir. Düşük güvenliler ayrıca işaretlenir. |
| Track var, tespit yok | Son nokta görüntü dışındaysa normal. İçindeyse "olası kaçırılmış tespit" olur; agent kırpma + vision veya düşük güvenli aday listesiyle (`stage2_final.csv`) kontrol eder. |
| Bir tespite birden fazla track yakın | Hungarian algoritması + mesafe kapısı. Belirsizse adaylar agent'a verilir. |
| Rapor hiçbir şeye bağlanmıyor | Bölge bağlamı olarak düşük ağırlıkla tutulur. |
| Aynı olay için birden fazla rapor | Birleştirilir. Bağımsız kaynaklar (official + third_party) uyumluysa güven artar. Çelişirlerse tespit hakem olur. |
| Yeni rapor formatı | Parser iddiayı `unknown` olarak etiketler, agent ham metinle inceler, log'a düşer. Sık görülürse kalıcı kural veya tool eklenir. |
| LLM hatası veya takılma | Şema doğrulaması, yeniden deneme, iterasyon limiti. En kötü durumda kural bazlı temel skor döner. |

## 8. Hız ve yol ağı tartışması

**Fikir:** Hızı ve ETA'yı araçların haritadaki gerçek yol üzerinden gittiğini varsayarak hesaplamak.

**Değerlendirme:**
- **Radyal hız ve üsse uzaklık yoldan bağımsızdır.** Tehdit için en kritik sinyal "üsse yaklaşıyor mu" sorusu ve bu kuş uçuşu mesafe değişimiyle doğru ölçülür.
  Görev tanımındaki örnek de kuş uçuşu mesafe ve hız kullanıyor. Değerlendirici büyük ihtimalle bu yöntemi bekliyor.
- **Track'ler seyrek (5 dk) ve sıçramalı.** Araçlar bir yerde ~10–25 m gürültüyle bekliyor, sonra 5 dakikada birkaç km sıçrıyor.
  5 dakikalık aralıklarla map-matching belirsiz, iki nokta arasında onlarca yol alternatifi olabilir.
- **Yol ağının asıl değer kattığı yer ETA.** Yol bazlı ETA, "üsse ne zaman varabilir" sorusuna daha gerçekçi cevap verir.
- **Maliyeti:** OSM verisinin indirilmesi ve önbelleğe alınması, map-matching, dış bağımlılık. Ayrıca verinin sentetik olması ihtimali var: noktalar yol üzerinde olmayabilir.

**Karar (onaylandı): yol ağı kullanılmayacak.**
1. Tüm metrikler **kuş uçuşu**: radyal hız, yer değiştirme hızı, ETA.
2. Ek olarak **yol uzunluğu hızı** (ardışık segmentlerin toplamı) ve **tortuosity** (yol / yer değiştirme oranı) hesaplanır.
   Bunlar, yol ağının getireceği faydanın çoğunu harita olmadan sağlar ve dolaşma davranışını ölçer.

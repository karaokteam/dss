# SUNUM — Ajan bölümü (4 dk) + Demo videosu (3 dk)

Dosya: `Sunum_Ajan_Bolumu.pptx` (hackathon şablonuyla; 5 slayt, sayfa no 04–08 → kapak + 2 YOLO slaytından sonra gelir).
Konuşma metinleri slaytların **konuşmacı notlarında** da var. Doldurulacaklar: `[TAKIM ADI]`, `[demo / repo bağlantısı]`.

## Akış (toplam 10 dk)
| Süre | Bölüm | Kim |
|---|---|---|
| 0:00–3:00 | Kapak + YOLO tespit hattı ve sonuçları | Arkadaşlar |
| 3:00–4:00 | **04 Problem**: Hangi araç gerçekten tehdit, ve neden? | Biz |
| 4:00–5:10 | **05 Mimari**: Kanıt önce, yapay zekâ sonra | Biz |
| 5:10–6:10 | **06 Örnek vaka**: T0122 | Biz |
| 6:10–7:00 | **07 Neden güvenilir** | Biz |
| 7:00–10:00 | **08 Demo videosu** | Video |

## Konuşma metni (sahnede okunacak; pptx notlarında da var)

**04 · Problem (60 sn)**

Arkadaşlarım aracı nasıl gördüğümüzü anlattı. Şimdi asıl soruya geliyoruz: Bu araçlardan hangisi gerçekten tehdit, ve bunu neye dayanarak söylüyoruz?

Bir üssü koruyan operatörü düşünün. Önünde iki saatlik bir tablo var: 40 drone görüntüsü, 226 aracın hareket kaydı ve sahadan gelen 137 rapor. İşin zor tarafı şu: raporlara güvenemiyorsunuz.

Sağdaki üç rakamı veriyi incelerken biz bulduk. "Bu araç bize bağlı, planlı ikmal" diyen 18 iddianın 17'si, üsse yaklaşan bir araç için yazılmış. Yani güven veren rapor, tam da dikkat edilmesi gereken aracın üstünü örtüyor.

226 aracın yalnızca 7'si iki saat boyunca her hareketinde üsse yaklaşıyor. Ve 5 araç üssün etrafında tur atıyor; bu tur fotoğraflar arasında olduğu için hiçbir fotoğrafta görünmüyor.

Yani tehdit "yaklaşan araç" değil; ısrarla yaklaşan ya da üssü turlayan araç. Ve bu araçlar, güven verici raporların arasında saklanıyor.

**05 · Mimari (70 sn)**

Bunu çözmek için tek bir ilkeyle yola çıktık: kanıt önce, yapay zekâ sonra.

Solda üç girdimiz var: YOLO tespitleri, araçların hareket kayıtları ve saha raporları.

Önce kurallarla çalışan bir hat, her görüntü için bir kanıt dosyası hazırlıyor.

Birinci adımda fotoğraftaki araçları hareket izleriyle eşleştiriyoruz. Böylece ağacın altında kaldığı için kameranın göremediği bir aracı bile izinden buluyoruz.

İkinci adımda her raporun anlattığı aracı fotoğrafta buluyor, iddiayı o aracın rapordan önceki yarım saatiyle sınıyoruz. Kimlik iddiası hiçbir zaman riski düşürmüyor.

Üçüncü adımda riski, her biri açıklanabilen faktörlerle puanlıyoruz: üssün etrafında dönme, tutarlı yaklaşma, varış süresi, araç tipi, yanıltıcı rapor.

Dördüncü adımda yapay zekâ analistimiz devreye giriyor. Kanıt dosyasını okuyor, yalnızca belirsiz noktalarda araştırıyor: bir bölgeyi sorguluyor, fotoğrafı yakınlaştırıyor. Ve yazdığı her cümleyi bir kanıt kimliğine bağlıyor.

Kısacası: zorunlu kanıtı yapay zekânın inisiyatifine bırakmıyoruz; yapay zekâyı gerçekten düşünmesi gereken yere koyuyoruz.

**06 · Örnek vaka: T0122 (60 sn)**

Bir örnekle göstereyim. Saat 14:10, Doğu Yolu.

Tespit modelimiz bu kamyonu yalnızca 0,10 güvenle görmüş. Sıradan bir sistem bu tespiti eleyip geçerdi.

Ama hareket kaydı başka bir şey söylüyor: Bu araç iki saatte 6 kilometreden 1,6 kilometreye gelmiş ve beş hareketinin beşi de üsse doğru.

Analistimiz fotoğrafı yakınlaştırıyor; görüntü de net değil. Ama sistemimiz tipe değil davranışa bakıyor: görüntü belirsiz, hareket kesin. Riski düşürmek için bir çürütme gerekir; belirsizlik yetmez.

Üstelik saat 12:35'te bu kamyon için "hareketleri olağan" diyen bir rapor var. O an kamyon gerçekten duruyor; ama raporun hemen ardından üsse 4,3 kilometre yaklaşıyor. Sistemimiz bu raporu riski düşüren bir bilgi değil, şüphe sinyali olarak işaretliyor.

Karar: kritik. Tahmini varış 26 dakika.

Sağ alttaki satıra dikkat: bu kararın her cümlesi tespite, ize ve rapora ait kimliklerle geri izlenebiliyor.

**07 · Neden güvenilir (50 sn)**

Peki bu sisteme neden güvenebilirsiniz? Üç sebep.

Birincisi, kanıt hiyerarşisi. Tespit izden, iz rapordan önce gelir. Her iddia kontrol edilebilir bir kimliğe bağlıdır; yapay zekâ var olmayan bir kimlik yazarsa sistem o cevabı kendisi reddeder.

İkincisi, kimlik varsaymaz. "Bu araç dost" iddiasını drone verisiyle teyit etmek mümkün değil; bu yüzden hiçbir rapor riski düşüremez. Kanıt yoksa "doğrulanamaz" deriz; tahmin yürütmeyiz.

Üçüncüsü, ölçülür. Ekibimizin elle etiketlediği 23 raporda kural katmanımız 22'sinde aynı hükme varıyor; yapay zekâ analistinin hükümleri de 13'ten 21'e çıktı. Dışarıdan bir gözden geçirmede bulunan beş açığı kapattık; üssün etrafında dönen araçları da böyle yakaladık.

Şimdi bunları operatörün ekranında görelim.

**08 · Demo anlatımı (Video 3 dk, video oynarken konuş)**

0:00 Bu, operatörün ekranı. Solda günün 40 olayı saat sırasıyla ve risk rengiyle; ortada harita; sağda seçili olayın fotoğrafı ve gerekçesi.

0:15 14:10 olayını açıyoruz. Üstteki bant neye bakmamız gerektiğini tek cümleyle söylüyor: T0122, üsse 1,6 kilometre. Oynatınca kamyonun son iki saatini izliyoruz: her sıçraması üsse doğru, sağ altta mesafe azalıyor. Raporlar sekmesinde 12:35'teki "hareketleri olağan" raporu şüpheli olarak işaretli.

1:10 Şimdi raporları sınayalım. R017 "Güney Kapısı yaklaşımında ağır araç yok" diyor. Rapora tıklayınca bölge morla işaretleniyor ve o andaki araçlar görünüyor. Aralarında bir kamyon var: rapor çelişkili. Sonra 15:25 olayı: T0034 kamyonu 14:45 ile 15:05 arasında üssün etrafında yarım kilometrede tur atıyor. Tam o sırada, 15:00'te, R042 "bölgede olağandışı bir şey yok" diyor. Sistem: çelişkili.

2:05 Tüm gün moduna geçiyoruz. Sabahtan akşama bütün araçlar ikonlarıyla hareket ediyor. Asistana soruyoruz: "Üssün etrafında dönen araçları göster." Asistan veriyi sorguluyor, beş aracı buluyor ve izlerini haritada birlikte çiziyor.

2:50 Son olarak T0188: ağacın altında olduğu için kameranın göremediği araç. Kesikli kutu yerini gösteriyor; hareket kaydı sayesinde yakaladık. Teşekkürler.

## Demo videosu — sahne planı (3 dk, slayt 08'deki zaman damgalarıyla aynı)
Sunucular: `.venv/bin/flask --app backend.api.app run --port 5000 --reload` ve `cd ui && npm run dev` → http://localhost:5173

| Zaman | Ekranda | Anlatım |
|---|---|---|
| 0:00–0:15 | Operasyon ekranı genel görünüm (sol olay akışı, orta harita, sağ detay) | "Operatörün tek ekranı: 40 olay saat sırasıyla, risk rengiyle." |
| **0:15**–1:10 | `#/image/img_000860` → bant: "En dikkat çeken: T0122…" → ▶ oynat: kamyon ikonu üsse yaklaşıyor → Araç sekmesi (6,0 → 1,6 km, 5↓/0↑, ETA) → Raporlar: R126 "hareketleri olağan" = kısmen + şüphe | "Her hareketinde üsse yaklaşan kamyon; 'olağan' raporu riski düşürmüyor, şüpheyi artırıyor." |
| **1:10**–2:05 | `#/image/img_004530?report=R017` → mor bölge + kamyon → "çelişkili". Sonra `#/image/img_007664` → bant "T0034 … 14:45–15:05 üssün etrafında döndü" → ▶ oynat (14:45–15:05 turu) → `#/image/img_001733?report=R042` "olağan" (15:00): mor bölgede T0034 → çelişkili | "Tur fotoğrafta görünmez; hareket kaydı yakalar. Aynı anda gelen 'olağan' raporu çelişkili." |
| **2:05**–2:50 | Zaman çubuğunda **Tüm gün** → ▶ → **Asistan**: "Üssün etrafında dönen araçları göster" → 5 aracın izi haritada | "Günün tamamı tek bakışta; asistan soruyu cevaplıyor ve haritayı yönetiyor." |
| 2:50–3:00 | T0188'i aç (`#/image/img_002900`): kesikli kutu, ağaç altında | "Kameranın göremediğini hareket kaydı yakaladı." |

Kayıt ipuçları: tarayıcıyı 1600×1000 veya tam ekran aç; Asistan cevabı ~20 sn sürebilir (kayıtta hızlandır ya da önceden sorup önbellekten tekrarla).

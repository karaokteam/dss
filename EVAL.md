# EVAL — 40 görüntünün değerlendirmesi

> Amaç: agent'ın kararlarının doğru olup olmadığını senin gözünle kontrol etmek.
> Notların hem prompt düzeltmesine hem de sunumdaki "doğrulama" bölümüne girecek.
> Aşağıdaki tabloda yalnızca **Senin hükmün** ve **Not** sütunlarını doldur, dosyayı bana gönder (ya da satırları yapıştır).

## Nasıl yapılır (görüntü başına 1–3 dk)

**Hazırlık:** Tarayıcıda `http://localhost:5173/#/image/<görüntü_id>` sayfasını aç. (Tablodaki bağlantılar doğrudan açar.)

**5 soru — sırayla bak:**

| # | Nereye bak | Soru | Tipik hata |
|---|---|---|---|
| 1 | **Fotoğraf + kutular** | Kutular gerçekten araçların üstünde mi? Kutusu olmayan belirgin bir araç ya da araç olmayan bir kutu var mı? | YOLO yanlış/eksik tespit |
| 2 | **En riskli araç** (kırmızı/turuncu kutuya tıkla → alttaki panel) | Bu araç gerçekten en tehlikelisi mi? *Hareket* satırında üsse yaklaşıyor mu, ne kadar yakın, kamyon mu? | Duran/uzaklaşan araca yüksek risk |
| 3 | **Araç panelinde "Agent kararı"** (temelden farklıysa "Sapma gerekçesi" var) | Seviyeyi değiştirme gerekçesi sayılarla ikna edici mi? | Gereksiz yükseltme |
| 4 | **Sağda "Bu görüntüye bağlı raporlar"** | Rapor metni ile yanındaki hüküm (Doğrulandı/Çelişkili...) mantıklı mı? | Yanlış araçla eşleştirme |
| 5 | **Sağ üstte agent özeti + Dikkat noktaları** | Özette kanıtta olmayan bir iddia var mı? Özellikle: *"koordineli / birlikte hareket"* ve *"tutarlı yaklaşma"* ifadeleri | Aşırı yorum (bildiğimiz sorun) |

**Hüküm seçenekleri (Senin hükmün sütunu):**
- `✅` doğru · `⬆` agent fazla DÜŞÜK vermiş · `⬇` agent fazla YÜKSEK vermiş · `❓` gerekçe hatalı ama seviye doğru · `👁` YOLO/görsel sorunu

**Bildiğimiz iki sorun (bunları ayrıca aramana gerek yok, gördüğünde ⬇ ya da ❓ işaretle):**
1. Tesadüfi hareket çakışmalarını "koordinasyon" diye yorumlayıp riski yükseltiyor (⚠ işaretli satırlar).
2. Her hareketinde yaklaşmayan araçlara da "tutarlı yaklaşma" diyor. Doğrusu: araç panelinde *Tutarlı yaklaşma: EVET* yazmıyorsa bu ifade yanlış.

**Zaman planı (~60 dk):** A grubu dikkatle (5 soru), B grubu hızlı (yalnızca 2 ve 5), C grubu göz atma (yalnızca 1).


## A grubu — Kritik / Yüksek (dikkatle, 5 soru) — 20 görüntü

| # | Görüntü | Saat | Bölge | Agent | Kural (temel) | En riskli araç | Dikkat | Senin hükmün | Not |
|---|---|---|---|---|---|---|---|---|---|
| A1 | [img_000860](http://localhost:5173/#/image/img_000860) | 14:10 | Dogu Yolu | **KRİTİK** | KRİTİK | T0122 truck | agent 4 aracı değiştirdi, ⚠ koordinasyon iddiası, 1 çelişkili iddia |  |  |
| A2 | [img_002256](http://localhost:5173/#/image/img_002256) | 14:05 | Kuzeybati Yolu | **YÜKSEK** | ORTA | T0088 car | agent 4 aracı değiştirdi, 3 çelişkili iddia |  |  |
| A3 | [img_007664](http://localhost:5173/#/image/img_007664) | 15:25 | Guney Kapisi Yaklasimi | **YÜKSEK** | ORTA | T0034 truck | agent 4 aracı değiştirdi, ⚠ koordinasyon iddiası, 2 çelişkili iddia |  |  |
| A4 | [img_005672](http://localhost:5173/#/image/img_005672) | 11:00 | Guneybati Yolu | **YÜKSEK** | ORTA | T0158 car | agent 3 aracı değiştirdi, ⚠ koordinasyon iddiası |  |  |
| A5 | [img_004388](http://localhost:5173/#/image/img_004388) | 12:55 | Kuzey Yolu | **YÜKSEK** | DÜŞÜK | T0137 car | agent 3 aracı değiştirdi, 2 çelişkili iddia |  |  |
| A6 | [img_003189](http://localhost:5173/#/image/img_003189) | 13:20 | Kuzeybati Yolu | **YÜKSEK** | ORTA | T0041 car | agent 3 aracı değiştirdi |  |  |
| A7 | [img_008333](http://localhost:5173/#/image/img_008333) | 10:10 | Kuzeydogu Kavsagi | **YÜKSEK** | ORTA | T0062 truck | agent 1 aracı değiştirdi, ⚠ koordinasyon iddiası, 1 çelişkili iddia |  |  |
| A8 | [img_000267](http://localhost:5173/#/image/img_000267) | 10:15 | Dogu Yolu | **YÜKSEK** | ORTA | T0045 truck | agent 1 aracı değiştirdi, 2 çelişkili iddia |  |  |
| A9 | [img_006388](http://localhost:5173/#/image/img_006388) | 10:35 | Kuzeybati Yolu | **YÜKSEK** | YÜKSEK | T0174 truck | agent 1 aracı değiştirdi, ⚠ koordinasyon iddiası, kaçırılmış araç |  |  |
| A10 | [img_004530](http://localhost:5173/#/image/img_004530) | 10:45 | Guney Kapisi Yaklasimi | **YÜKSEK** | ORTA | T0165 car | agent 1 aracı değiştirdi, ⚠ koordinasyon iddiası, 2 çelişkili iddia |  |  |
| A11 | [img_000926](http://localhost:5173/#/image/img_000926) | 11:35 | Kuzeydogu Kavsagi | **YÜKSEK** | YÜKSEK | T0154 car | agent 1 aracı değiştirdi, ⚠ koordinasyon iddiası, 2 çelişkili iddia |  |  |
| A12 | [img_000733](http://localhost:5173/#/image/img_000733) | 13:00 | Guney Kapisi Yaklasimi | **YÜKSEK** | ORTA | T0190 car | agent 1 aracı değiştirdi, 3 çelişkili iddia |  |  |
| A13 | [img_003839](http://localhost:5173/#/image/img_003839) | 13:25 | Kuzey Yolu | **YÜKSEK** | YÜKSEK | T0183 car | agent 1 aracı değiştirdi, 1 çelişkili iddia |  |  |
| A14 | [img_002900](http://localhost:5173/#/image/img_002900) | 13:50 | Bati Yerlesimi | **YÜKSEK** | YÜKSEK | T0188 ? | agent 1 aracı değiştirdi, ⚠ koordinasyon iddiası, kaçırılmış araç |  |  |
| A15 | [img_003201](http://localhost:5173/#/image/img_003201) | 14:55 | Guney Kapisi Yaklasimi | **YÜKSEK** | ORTA | T0213 bus | agent 1 aracı değiştirdi, 3 çelişkili iddia |  |  |
| A16 | [img_001230](http://localhost:5173/#/image/img_001230) | 15:15 | Guneydogu Yerlesimi | **YÜKSEK** | ORTA | T0031 car | agent 1 aracı değiştirdi, ⚠ koordinasyon iddiası, 1 çelişkili iddia |  |  |
| A17 | [img_005368](http://localhost:5173/#/image/img_005368) | 10:25 | Dogu Yolu | **YÜKSEK** | YÜKSEK | T0019 truck | ⚠ koordinasyon iddiası, 2 çelişkili iddia |  |  |
| A18 | [img_006673](http://localhost:5173/#/image/img_006673) | 10:30 | Guneydogu Yerlesimi | **YÜKSEK** | YÜKSEK | T0091 car | ⚠ koordinasyon iddiası, 4 çelişkili iddia |  |  |
| A19 | [img_003464](http://localhost:5173/#/image/img_003464) | 12:15 | Kuzey Yolu | **YÜKSEK** | YÜKSEK | T0135 truck | ⚠ koordinasyon iddiası |  |  |
| A20 | [img_001733](http://localhost:5173/#/image/img_001733) | 15:05 | Kuzeybati Yolu | **YÜKSEK** | YÜKSEK | T0121 van | ⚠ koordinasyon iddiası |  |  |

## B grubu — Orta (hızlı: soru 2 ve 5) — 15 görüntü

| # | Görüntü | Saat | Bölge | Agent | Kural (temel) | En riskli araç | Dikkat | Senin hükmün | Not |
|---|---|---|---|---|---|---|---|---|---|
| B1 | [img_002661](http://localhost:5173/#/image/img_002661) | 14:00 | Kuzey Yolu | **ORTA** | ORTA | T0010 truck | agent 3 aracı değiştirdi |  |  |
| B2 | [img_004423](http://localhost:5173/#/image/img_004423) | 15:50 | Kuzeybati Yolu | **ORTA** | ORTA | T0076 truck | agent 2 aracı değiştirdi |  |  |
| B3 | [img_005978](http://localhost:5173/#/image/img_005978) | 10:20 | Guneybati Yolu | **ORTA** | DÜŞÜK | T0153 car | agent 1 aracı değiştirdi |  |  |
| B4 | [img_005788](http://localhost:5173/#/image/img_005788) | 11:10 | Bati Yerlesimi | **ORTA** | ORTA | T0104 car | agent 1 aracı değiştirdi, ⚠ koordinasyon iddiası |  |  |
| B5 | [img_008001](http://localhost:5173/#/image/img_008001) | 14:25 | Dogu Yolu | **ORTA** | ORTA | img_008001_008 truck | agent 1 aracı değiştirdi, 2 çelişkili iddia |  |  |
| B6 | [img_006444](http://localhost:5173/#/image/img_006444) | 15:35 | Guneybati Yolu | **ORTA** | DÜŞÜK | img_006444_006 bus | agent 1 aracı değiştirdi, 2 çelişkili iddia |  |  |
| B7 | [img_006591](http://localhost:5173/#/image/img_006591) | 11:15 | Bati Yerlesimi | **ORTA** | ORTA | T0118 car | ⚠ koordinasyon iddiası, 1 çelişkili iddia |  |  |
| B8 | [img_005359](http://localhost:5173/#/image/img_005359) | 11:30 | Guneydogu Yerlesimi | **ORTA** | ORTA | T0195 car | 2 çelişkili iddia |  |  |
| B9 | [img_000531](http://localhost:5173/#/image/img_000531) | 12:05 | Guneybati Yolu | **ORTA** | DÜŞÜK | T0113 car | 2 çelişkili iddia |  |  |
| B10 | [img_005561](http://localhost:5173/#/image/img_005561) | 12:10 | Guney Kapisi Yaklasimi | **ORTA** | ORTA | T0042 car | ⚠ koordinasyon iddiası |  |  |
| B11 | [img_004512](http://localhost:5173/#/image/img_004512) | 13:05 | Kuzeydogu Kavsagi | **ORTA** | DÜŞÜK | T0014 car | ⚠ koordinasyon iddiası, 1 çelişkili iddia |  |  |
| B12 | [img_008562](http://localhost:5173/#/image/img_008562) | 14:20 | Guneydogu Yerlesimi | **ORTA** | ORTA | T0194 car | 1 çelişkili iddia |  |  |
| B13 | [img_007171](http://localhost:5173/#/image/img_007171) | 15:00 | Kuzeydogu Kavsagi | **ORTA** | ORTA | T0052 car | ⚠ koordinasyon iddiası |  |  |
| B14 | [img_001147](http://localhost:5173/#/image/img_001147) | 15:20 | Guneybati Yolu | **ORTA** | ORTA | T0060 car | ⚠ koordinasyon iddiası, 2 çelişkili iddia |  |  |
| B15 | [img_004318](http://localhost:5173/#/image/img_004318) | 15:45 | Bati Yerlesimi | **ORTA** | ORTA | T0081 truck | 3 çelişkili iddia |  |  |

## C grubu — Düşük (göz at: soru 1) — 5 görüntü

| # | Görüntü | Saat | Bölge | Agent | Kural (temel) | En riskli araç | Dikkat | Senin hükmün | Not |
|---|---|---|---|---|---|---|---|---|---|
| C1 | [img_008589](http://localhost:5173/#/image/img_008589) | 10:40 | Dogu Yolu | **DÜŞÜK** | DÜŞÜK | T0082 car | ⚠ koordinasyon iddiası, 1 çelişkili iddia, kaçırılmış araç |  |  |
| C2 | [img_005611](http://localhost:5173/#/image/img_005611) | 13:45 | Bati Yerlesimi | **DÜŞÜK** | DÜŞÜK | T0123 car | ⚠ koordinasyon iddiası |  |  |
| C3 | [img_004416](http://localhost:5173/#/image/img_004416) | 14:15 | Guneydogu Yerlesimi | **DÜŞÜK** | DÜŞÜK | T0162 car | ⚠ koordinasyon iddiası, 1 çelişkili iddia |  |  |
| C4 | [img_003880](http://localhost:5173/#/image/img_003880) | 14:35 | Kuzeydogu Kavsagi | **DÜŞÜK** | DÜŞÜK | T0211 car | - |  |  |
| C5 | [img_001643](http://localhost:5173/#/image/img_001643) | 15:10 | Kuzey Yolu | **DÜŞÜK** | DÜŞÜK | T0094 car | 1 çelişkili iddia |  |  |

## Genel notlar (isteğe bağlı)
- Harita / UI'da kafa karıştıran yerler:
- Sunumda göstermek istediğin güçlü örnekler (görüntü id):
- Başka:

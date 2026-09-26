# Rapor Doğrulama ve Bölge Entegrasyonu — Tasarım Notu

> **Güncelleme (yeni mimari, Kişi 4):**
> - Kod hüküm vermez, ölçer. §4.3'teki ✓/◐/✗/? sonuçları kanıt paketine girmez; hükmü LLM `ReportVerdict` ile verir, validator denetler. Kural tabanlı hüküm sadece değerlendirme için `eval/baseline.py`'de durur.
> - Rapor kimlikleri 1'den başlıyor (`R001`). Bu dokümanın ilk sürümündeki R042 = R043.
> - Yeni bulgu: rapor koordinatları **çekim anındaki** bir aracın konumu (5 hane 0–1 m, 4 hane ≤10 m). Kontroller "hedef araç" üzerinden yapılıyor.
> - Uygulama: `dss/reports/` (`claims`, `association`, `checks`, `trace`). Etiketli set ve değerlendirme: `eval/gold_reports.json`, `eval/run_eval.py`. Şema önerisi: `docs/SCHEMA_PROPOSAL_REPORTS.md`.
> - **Bölge raporları (§5'in uygulanmış hali):** Bölge iddiaları tek karede değil, bütün bölgede ve rapor anı ±15 dk içinde ölçülüyor (`dss/reports/zone_checks.py`). Track'lere sınıf, ≤3 m eşleşen tespitten taşınıyor (0,10 eşiği, 201/226 track). "Olağandışı" = sert bayrak koşulu. "Sabah devriyesi" raporları bağlama geçti. Yön sektörü ile en yakın bölge merkezi track noktalarının %100'ünde aynı sonucu verdiği için §5.2'deki Z1/Z2 tartışması kapandı. Ayrıntılar: `docs/SCHEMA_PROPOSAL_REPORTS.md` §5.
> - Sayı düzeltmesi: koordinatlı rapor 72 (B2'deki 54 + 18 dost/kimlik). Bölge adlı 43 raporun 22'si bölge iddiası, 21'i bağlam.
> - Aşağıdaki step kimlikleri (RAP-2, TRK-1…) ve keşif haritası eski iskelete aitti; yeni yapıda Kişi 1–6 dağılımı geçerli.

> **Durum:** Tartışma taslağı, 2026-09-26. Karar verilmesi gerekenler §7'de.
> **İlgili step'ler:** RAP-2 (çıkarım), RAP-3 (doğrulama), RSK-3 (rapor kuralları), LLM-2 (brief), TRK-1 (eşleştirme), DET-4 (eşik).
> **Keşif haritası:** `python -m exploration.map.build_map` → `exploration/map/index.html` (§8).

## Özet

- Saha raporlarını LLM'e "hepsini kıyasla" diye vermiyoruz. Her raporu **zaman aralığı olan küçük iddialara** bölüyoruz, bu iddiaları **Python'da** track ve tespitlerle kontrol ediyoruz. LLM'e kontrol sonuçlarının tablosunu veriyoruz; LLM tartıyor ve gerekçelendiriyor.
- Kontrolün dört sonucu var: ✓ doğrulandı · ◐ kısmen · ✗ çelişki · ? doğrulanamaz. "Uzun süredir duruyor", "dün gece" gibi zaman ifadeleri bu sayede doğru ele alınıyor.
- **Bölgeler (zones)** nokta değil; üssün etrafında 45°'lik 8 koridor. Bir konumun bölgesi, üsse göre yönüyle (sektör) ve üsse mesafesiyle (halka) belirlenir.
- Keşifte çıkan iki kritik bulgu:
  1. Referans tehdit (img_000860'taki kamyon, T0122) sadece **0,10** güvenle tespit ediliyor; 0,25 eşiği onu kaçırıyor.
  2. **Üsse yaklaşmak tek başına ayırt edici değil**: 226 track'in 103'ü son 30 dakikada üsse 500 m'den fazla yaklaşıyor.

---

## 1. Elimizdeki veri

| Veri | Sayı | Not |
|---|---|---|
| Görüntü | 40 | 8 koridor × 5 görüntü; üsse 1,6 / 2,6 / 3,5 / 4,4 / 5,4 km mesafede. Boyutlar: 960×540, 1360×765, 1920×1080 |
| Track | 226 × 25 nokta | 5 dakikalık adımlarla 2 saat. Her track, ait olduğu görüntünün çekim anında biter |
| Tespit (`data/image_box_and_reports/`) | ≥0,25 güven: 254 · ≥0,10 güven: 323 | Takımın 1. gün modelinin çıktısı (Kaggle public LB 0,82093). Kutu merkezinin lat/lon'u da dosyada var |
| Rapor | 137 | 98 official, 39 third_party. Saat aralığı 08:35–15:15. Sadece **32 kalıptan** üretilmiş |
| Bölge | 8 + Merkez Üs | Bölge merkezleri üsse 3,2 km mesafede, 0°, 45°, …, 315° yönlerinde |

---

## 2. Keşif bulguları

**B1 · Raporlar şablondan üretilmiş.** 137 raporun hepsi 32 kalıptan birine uyuyor. Bu yüzden rapor metnini iddialara çevirmek için regex yeterli; ucuz, hızlı ve her seferinde aynı sonucu veriyor. LLM ancak yeni ya da farklı yazılmış bir cümle gelirse yedek olarak kullanılır.

**B2 · Raporlar dört grupta toplanıyor.**

| Grup | Örnek | ~Adet | Doğrulanabilir mi? |
|---|---|---|---|
| Koordinatlı araç iddiası | "…civarında 2 kamyon görüldü", "…uzun süredir hareketsiz duruyor" | 54 | Evet: konum, zaman ve hareket track'ten; tip ve sayı tespitten |
| Kimlik / dost iddiası | "üsse gelen otomobil bize bağlı unsurdur", "ikmal aracı, kimlik teyitli", "dost devriye" | 18 | **Kimlik hayır**, hareket kısmı evet |
| Bölge adıyla genel ifade | "Kuzey Yolu'nda trafik normal", "ağır araç yok, yalnızca binek" | 43 | Kısmen: o bölgedeki track'ler ve görüntüler ile |
| Konu dışı | hava durumu, konvoy planı, genel "tatbikat" duyurusu | 22 | Hayır, skora girmez |

**B3 · Kaynak türü doğruluğu göstermiyor.** Dost/kimlik iddialarının **18'inin 18'i de `official`** kaynaklı. "Üsse doğru ilerleyen ikmal aracı" denen noktalardaki track'lerin çoğu o saatte **duruyor**. Kaynak türünü güvenilirlik ölçüsü olarak kullanırsak tam bu tuzağa düşeriz.

**B4 · Koordinatlı 72 raporun 72'si de en az bir görüntünün karesinin içinde.** Yani her koordinatlı rapor bir görüntüye bağlanabiliyor; tip ve sayı iddiaları o görüntünün tespitleriyle kontrol edilebilir. Rapor saati ile çekim saati arasındaki fark 5–120 dakika.

**B5 · Tespit–track eşleşmesi çok sıkı.** Çekim anında görüntü karesinin içinde olan 206 track'in 201'i bir tespitle eşleşti. Eşleşme mesafesi: yarısında 0,2 m'nin altında, %90'ında 0,9 m'nin altında. 15 m'yi aşan 7 eşleşmenin hepsi düşük güvenli tespitlerde ve büyük ihtimalle hatalı. → `MATCH_MAX_DIST_M` için 10 m yeterli.

**B6 · Referans tehdit düşük güvenle tespit ediliyor.** img_000860'taki kamyon (piksel 754, 300) sadece **0,10** güvenle bulunuyor ve T0122 ile 0,3 m içinde eşleşiyor. 0,25 eşiğiyle çalışsaydık günün en kritik aracını kaçırırdık.
→ Öneri: **track destekli kabul.** Düşük güvenli bir tespit bir track noktasıyla birkaç metre içinde çakışıyorsa gerçek araç sayılır. Sınıf etiketine ise güven değeriyle orantılı ağırlık verilir; brief'te "tip belirsiz, muhtemelen kamyon" gibi yazılır.

**B7 · Üsse yaklaşmak tek başına ayırt edici değil.** Son 30 dakikada 103 track üsse 500 m'den fazla yaklaşıyor, çünkü yollar üsse çıkıyor. Asıl ayırt edici olanlar:
- Uzun beklemeden sonra ani hareket. T0122 12:10–13:55 arasında Kuzey / Kuzeydoğu koridorunda ~5,45 km'de bekliyor; 14:10'da Doğu Yolu'nda üsse 1,65 km mesafede (son 5 dakikada ~8 m/s).
- İç halkaya (≤2 km) girmek, koridor değiştirmek.
- Aracın sınıfı (kamyon/otobüs).
- Hakkındaki raporun çelişkili olması.

**B8 · Raporlar anlık görüntüdür, sonrasında durum değişebilir.** 13:40'ta bir noktada "yüklü kamyon uzun süredir park halinde" deniyor. O noktadaki T0126 gerçekten bekliyor, yani rapor doğru. Ama aynı noktadaki T0122 30 dakika sonra üsse 1,6 km mesafede. Bu yüzden her iddia **hem rapor anında hem çekim anında** kontrol edilmeli.

---

## 3. Seçenekler

| | **A · Her şeyi LLM'e ver** | **B · LLM track'i analiz etsin, sonra raporla kıyaslasın** | **C · İddiaları Python doğrulasın, LLM tartsın (öneri)** |
|---|---|---|---|
| Ne yapılır | Görüntü + 25 satırlık track'ler + raporlar tek promptta, "kıyasla" | LLM track'i bizim tanımladığımız durumlara göre özetler, sonra raporla kıyaslar | Rapor → iddialar (regex, gerekirse LLM) → Python kontrolü → sonuç tablosu → LLM hakem ve anlatıcı |
| Sayısal doğruluk | Düşük: LLM haversine hesabını kafadan yapar, 4,4 km'lik bir yer değiştirmeyi kaçırabilir | Orta: özetleme doğru olsa bile hız/mesafe hesabı LLM'de kalır | Yüksek: tüm hesaplar test edilmiş kodda |
| Açıklanabilirlik | Zayıf: "model öyle dedi" | Orta | Güçlü: her iddianın kanıtı ve kapsama oranı var |
| Aynı girdiye aynı sonuç | Hayır | Kısmen | Evet (sadece anlatım kısmı değişir) |
| Maliyet ve süre | Görüntü başına büyük context, 10–30 sn | Track başına ayrı çağrı, çok sayıda çağrı | Görüntü başına tek çağrı, küçük context |
| Yeni tip rapora dayanıklılık | Yüksek | Yüksek | Yüksek (LLM çevirici yedeği sayesinde) |
| Mentor ve jüri açısından | "Tamamen LLM'e bırakmışlar" | Karışık | "Sayılar koddan, muhakeme LLM'den" |

**Neden C?** Kullanıcının öne sürdüğü iki seçenek A ve B'ye karşılık geliyor. C, B'nin iyi fikrini ("bizim belirlediğimiz durumlara göre analiz") alıp analizi LLM yerine koda veriyor. LLM'e kalan iş, kodun iyi yapamadığı şeyler: yeni ifadeleri anlamak, zayıf sinyalleri birlikte tartmak ve gerekçeli bir metin yazmak.

C'nin iki çeşidi var:
- **C1:** iddialar sadece regex ile çıkarılır.
- **C2:** regex, gerekirse LLM yedeği (**öneri**). Jüri demoda farklı bir cümle yazarsa sistem kırılmaz.

---

## 4. Önerilen akış (C2)

```
rapor metni ──regex (+LLM yedeği)──► İddialar[]  ──┐
track'ler, tespitler, görüntüler ─────────────────┼─► Python kontrolü ─► Sonuç tablosu ─┐
bölgeler ─────────────────────────────────────────┘                                     ├─► LLM: tart + gerekçelendir ─► brief
risk kuralları (factors) ──────────────────────────────────────────────────────────────┘      (sayı üretmez, seviye değiştirmez)
```

### 4.1 İddia kataloğu

Her iddianın bir **konumu** (nokta + yarıçap ya da bölge) ve bir **zaman aralığı** var.

| İddia | Parametreler | Nasıl kontrol edilir | Varsayılan eşik |
|---|---|---|---|
| `VAR` | konum, t, [tip], [sayı] | t anında konumdaki track'ler (alt sınır) + t'ye en yakın görüntüdeki tespitler | yarıçap 75 m |
| `HAREKETSIZ` | konum, [t−süre, t] | Aralıkta track'in en büyük yer değiştirmesi | ≤ 20 m |
| `HAREKETLI` | konum, t | Son 15 dakikadaki hız | ≥ 1 m/s |
| `USSE_YAKLASIYOR` | konum, t | Son 30 dakikada üsse mesafe azalması | ≥ 300 m |
| `UZAKLASIYOR` | konum, t | Son 30 dakikada üsse mesafe artışı | ≥ 300 m |
| `SAYI` | konum, t, n, [tip] | Görüntüdeki tespit sayısı (track yeterli değil: park halindeki araçların kaydı olmayabilir) | ±1 tolerans |
| `TIP` | konum, t, sınıf | Görüntüdeki tespitin sınıfı (+ yedek etiketler) | güven ≥ 0,25 ya da track destekli |
| `BOLGE_DURUMU` | bölge, t, seviye | Bölgedeki track sayısı ve hareketi + ±30 dk içindeki görüntülerin tespitleri | §5 |
| `KIMLIK` | konum, "dost/ikmal/devriye" | **Doğrulanamaz**, tasarım gereği | — |
| `GECMIS_OLAY` | "dün gece", "sabah" | **Doğrulanamaz**: veri kapsamı dışında | — |
| `GORSEL_DETAY` | "yüklü", "üzeri örtülü", renk | Şimdilik doğrulanamaz (ileride LLM görüntü okuması, OI-LLM-3) | — |

Zaman ifadelerinin karşılığı: "uzun süredir" → 60 dk · "bir saatten uzun süredir" → 60 dk · "40 dakikadır" → 40 dk · "dün gece" → `GECMIS_OLAY`. Track'ler 2 saatlik olduğu için daha uzun süreler en fazla ◐ kısmen doğrulanabilir.

### 4.2 Kalıp → iddia eşlemesi (32 kalıbın özeti)

| Kalıp (ör.) | İddialar |
|---|---|
| `<K> civarinda <N> <TIP> goruldu` · `…bulundugu yonunde ihbar` · `…gozlendi` · `…oldugu bildirildi` | `VAR` + `SAYI` + `TIP` |
| `<K> civarinda bir <TIP> uzun suredir hareketsiz duruyor` · `…bir saatten uzun suredir yerinden ayrilmadi` · `…park halinde` · `…beklemede` · `…durdugu bildirildi` | `VAR` + `TIP` + `HAREKETSIZ(60)` (+`SAYI`) |
| `<K> konumundan usse dogru ilerleyen <TIP> planli ikmal araci…` · `…usse gelen <TIP> bize bagli unsurdur` | `VAR` + `TIP` + `USSE_YAKLASIYOR` + `KIMLIK(dost)` |
| `<K> civarindaki <RENK> arac dost devriye…` | `VAR` + `KIMLIK(dost)` + `GORSEL_DETAY(renk)` |
| `…transit geciyor` · `…bolgeden uzaklasiyor` | `VAR` + `TIP` + `HAREKETLI` / `UZAKLASIYOR` |
| `…<N> araclik bir kamyon konvoyu ilerliyor` | `VAR` + `SAYI` + `TIP` + `HAREKETLI` |
| `…hareketleri olagan` · `…trafik olagandan yogun; genellikle <N> arac` | `VAR` + `SAYI` (+ normal durum karşılaştırması) |
| `<B> bolgesinde trafik akisi normal` · `…kayda deger hareketlilik yok` · `…olagandisi durum bildirmedi` | `BOLGE_DURUMU(normal)` |
| `<B> bolgesinde agir arac hareketi yok, yalnizca binek` | `BOLGE_DURUMU(agir_arac=0)` |
| `Dun gece <B> cevresinde … dogrulanmamis ihbar` · `<B> … ihbar incelendi, dogrulanamadi` | `GECMIS_OLAY` (bilgi amaçlı) |
| `<B> … devriyeyle telsiz baglantisi <N> dakikadir kurulamiyor` | **Bağlam:** o bölgede gözlem eksik. Belirsizliği artırır, skoru düşürmez |
| Hava durumu · konvoy planı · "tatbikat nedeniyle dost unsurlar" | Konu dışı / genel `KIMLIK` → skora girmez |

Tam liste RAP-2 step'inde `agent/reports/lexicon.py` ve testlere işlenecek.

### 4.3 Sonuçlar ve raporun genel hükmü

- Her iddia için: `status` (✓ / ◐ / ✗ / ?), `coverage` (istenen aralığın ne kadarı veride var), `evidence` (okunabilir gerekçe) ve varsa `track_id` / `detection_id`.
- Raporun genel hükmü:
  - En az bir ✗ varsa → **çelişkili**.
  - Hiç ✗ yoksa ve kontrol edilebilen iddiaların hepsi ✓ ise → **doğrulandı**.
  - Karışıksa → **kısmen**.
  - Hiçbiri kontrol edilemiyorsa → **doğrulanamaz**.
- `KIMLIK` iddiası genel hükmü hiçbir zaman "doğrulandı" yapamaz. En iyi ihtimalle "hareket kısmı doğrulandı, kimlik doğrulanamaz" olur.

### 4.4 Raporu bir araca ve görüntüye bağlamak

1. **Görüntü:** Rapor noktasını karesinin içine alan görüntüler; bunlardan zamanı en yakın olan seçilir (B4).
2. **Araç:** Rapor anında yarıçap içindeki track adayları. Rapor iddialarıyla **en uyumlu** aday seçilir (B8: T0126 ile T0122 aynı noktada).
3. **İki kontrol zamanı:** her iddia rapor anında ve çekim anında ayrı ayrı kontrol edilir. "Rapor yazıldığında doğruydu, çekim anında geçersiz" durumu açıkça raporlanır.

### 4.5 Kaynak türü (official / third_party)

- Kanıt değil, **küçük bir ön güvendir**. Verinin kanıtı her zaman kaynağın önüne geçer.
- Güven verici iddialar (`KIMLIK`, "olağandışı yok") kaynak ne olursa olsun **skoru düşürmez** (README ilke 2).
- Tehdit bildiren bir iddia ✓ olursa puan ekler. third_party ise ağırlığı biraz daha düşük tutulabilir (§7, K3).
- Brief'te kaynak her zaman açıkça yazılır.

### 4.6 LLM'e gidecek kanıt paketi (görüntü başına, örnek)

```json
{
  "image": {"id": "img_000860", "time": "14:10", "zone": "Dogu Yolu", "ring_km": 1.6},
  "vehicles": [
    {
      "id": "img_000860_006", "class": "truck", "confidence": 0.10, "track_supported": true,
      "track": "T0122", "match_m": 0.3,
      "motion": "12:10–13:55 ~5,45 km'de bekledi (Kuzey→Kuzeydoğu koridoru); 13:55–14:10 arası 3,8 km yol aldı, son 5 dk ~8 m/s; şimdi Doğu Yolu, üsse 1,65 km, yaklaşıyor",
      "risk": {"level": "HIGH", "factors": [{"name": "motion.sudden_departure", "points": 30, "reason": "..."}]}
    }
  ],
  "reports": [
    {
      "id": "R043", "time": "13:40", "source": "third_party",
      "text": "…yuklu bir kamyonun uzun suredir park halinde…",
      "claims": [
        {"type": "HAREKETSIZ", "status": "partial", "coverage": 0.54, "track": "T0126", "evidence": "T0126 son 65 dk'da 11 m oynadı"},
        {"type": "GORSEL_DETAY", "status": "unverifiable"}
      ],
      "drift_at_capture": "Aynı noktadaki T0122 14:10'da üsse 1,6 km'de; rapor bu aracı kapsamıyor"
    }
  ],
  "zone_context": {"Dogu Yolu": {"recent_reports": 2, "radio_gap": false}}
}
```

### 4.7 Sistem promptu (taslak ilkeler)

1. **Rol:** Üs koruma analisti. Görevin, verilen kanıt paketine dayanarak hangi durumların dikkat gerektirdiğini gerekçelendirmek.
2. **Sayılar:** Sadece paketteki sayıları kullan. Mesafe, hız ya da süre hesaplama.
3. **Seviye:** `risk.level` değişmez. Katılmıyorsan `note` alanına yaz, seviyeyi değiştirme.
4. **Raporlar iddiadır:** Kaynak türü (official/third_party) doğruluk kanıtı değildir. Kimlik ve "dost" iddiaları veriyle doğrulanamaz ve riski azaltmaz.
5. **Çelişki olursa tespit esas alınır** (görev tanımı).
6. **Belirsizliği açıkça yaz:** ◐ ve ? sonuçlarını "doğrulandı" gibi anlatma.
7. **Çıktı biçimi:** JSON: `summary`, `attention[]` (araç id + gerekçe + dayandığı kanıt id'leri), `report_assessment[]` (rapor id + hüküm + tek cümle), `uncertainties[]`. Her cümle bir id'ye dayanmalı.
8. **Kısa ve Türkçe.**

---

## 5. Bölgelerin (zones) entegrasyonu

### 5.1 Bölgenin gerçek geometrisi

- 8 bölge merkezi, üssün etrafında 3,2 km yarıçaplı bir çemberde, 45° aralıklarla (K, KD, D, GD, G, GB, B, KB).
- Her bölgede **tam 5 görüntü** var ve bunlar üsten dışarı doğru bir hat üzerinde dizili: ~1,6 / 2,6 / 3,5 / 4,4 / 5,4 km.
- Yani bölge bir nokta değil, **üsse uzanan bir yaklaşma koridoru**. İsimler de bunu gösteriyor: "Kuzey Yolu", "Güney Kapısı Yaklaşımı".

### 5.2 Bir konumun bölgesini belirleme seçenekleri

| Seçenek | Tanım | Artısı | Eksisi |
|---|---|---|---|
| Z1 · En yakın merkez | Konum hangi bölge merkezine en yakınsa | En basit yöntem | Merkezler 3,2 km'de. İç ve dış halkadaki noktalarda sınırlar bozulabiliyor |
| **Z2 · Yön sektörü + halka (öneri)** | Bölge = üsse göre yön (±22,5°); halka = üsse mesafe (≤2 / 2–3 / 3–4 / 4–5 / >5 km) | Koridor mantığına uyuyor. Her konum için tanımlı, açıklaması kolay ("Doğu Yolu, 1,6 km halkası") | Yok denecek kadar az. Sınıra çok yakın noktalar için iki bölge adı birlikte verilebilir |
| Z3 · Sadece görüntü kareleri | Bölge = o bölgenin 5 görüntüsünün karesi | Tespit verisiyle birebir örtüşüyor | Görüntü dışındaki araçlar (track'lerin çoğu) bölgesiz kalıyor |

Veride Z1 ve Z2 görüntüler için aynı sonucu veriyor (her bölgeye 5 görüntü düşüyor). Z2'yi seçmenin sebebi, track noktaları için de tutarlı bir tanım sağlaması.

### 5.3 Bölgenin kullanılacağı yerler

1. **Bölge adıyla yazılmış raporlar (43 rapor):**
   - "Trafik normal" / "olağandışı yok" → rapor anında o sektördeki track'lerde anormal hareket (iç halkaya hızlı giriş, uzun bekleme sonrası kalkış) var mı?
   - "Ağır araç yok, yalnızca binek" → o sektörde ±30 dakika içinde çekilmiş görüntülerde kamyon/otobüs tespiti var mı?
   - Kapsama: 43 raporun hepsinde rapor anında o bölgede en az bir track var. Aynı bölgede ±30 dakika içinde görüntü olanlar 26, ±60 dakika içinde 34. Kalanlar sadece track'le kontrol edilir; tip iddiaları "?" kalır.
2. **Araç bağlamı:** hangi koridorda, hangi halkada; koridor boyunca içeri mi ilerliyor (radyal hız); koridor değiştirdi mi (T0122: Kuzey → Kuzeydoğu → Doğu).
3. **Risk kuralları (RSK-1, RSK-2):** iç halkaya giriş (≤2 km); uzun beklemeden sonra ani hareket; aynı koridorda kısa sürede birden fazla ağır araç; o bölgede telsiz kopukluğu varsa belirsizlik notu.
4. **Arayüz:** 8 koridorluk bir "bölge durum" paneli (seviye, son rapor, son görüntü saati). Jüri tarafında ürün değeri yüksek.
5. **Brief dili:** koordinat yerine "Doğu Yolu koridorunda, üsse 1,6 km".

### 5.4 Uygulama

- `agent/geo/zones.py` (yeni, GEO hattına eklenebilir):
  - `sector(point) → bölge adı`
  - `ring(point) → halka`
  - `radial_speed(track) → içe/dışa hız`
- Saf fonksiyonlar; `spatial.py` gibi herkes kullanabilir. Şemaya `GeoDetection.ring_km` ve `MotionProfile.corridor_path` alanları eklenebilir (varsayılan değerli, `[SCHEMA]` PR).

---

## 6. Diğer sonuçlar (koda yansıyacaklar)

| Konu | Öneri | Step |
|---|---|---|
| Eşleşme mesafesi | `MATCH_MAX_DIST_M = 10` (B5) | TRK-1 |
| Düşük güvenli tespit | Track destekli kabul: ≥0,10 güven + ≤3 m track eşleşmesi → araç sayılır (B6) | DET-4, TRK-1 |
| Tespit kaynağı | Agent `data/image_box_and_reports/detections_all_ge0.10.json`'ı cache olarak okuyabilir; demo için model gerekmez | DET-3 |
| "Yaklaşıyor" kuralı | Tek başına az puan. Ani kalkış, iç halka ve sınıf ile birleşince yüksek puan (B7) | RSK-2 |
| Zaman kayması | Her iddia hem rapor hem çekim anında kontrol edilir (B8) | RAP-3 |

---

## 7. Karar verilmesi gerekenler

| # | Karar | Önerim |
|---|---|---|
| K1 | Yöntem: A / B / C1 / C2 | **C2** |
| K2 | Bölge tanımı: Z1 / Z2 / Z3 | **Z2** (sektör + halka) |
| K3 | third_party kaynaklı ve doğrulanmış tehdit iddiasının ağırlığı | official'ın %70'i; güven verici iddialar her durumda 0 |
| K4 | Düşük güvenli tespitin track destekli kabulü | Evet: ≥0,10 güven + ≤3 m |
| K5 | ◐ kısmen doğrulanmış tehdit iddiası puan eklesin mi? | Evet, ✓'nin yarısı |
| K6 | Bölge durum paneli arayüze girsin mi? | Evet (UI-3'ün bir parçası olarak) |

Kararlar verilince `PROGRESS.md` → Kararlar bölümüne taşınır; eşikler `agent/config/*` altına yazılır.

---

## 8. Keşif haritası

```bash
python -m exploration.map.build_map     # → exploration/map/index.html, tarayıcıda aç
```

- **Zaman kaydırıcısı / ▶:** araçların o andaki konumları (siyah nokta), son 2 saatlik izleri, seçili saatten önceki 60 dakikanın raporları (solda liste, haritada halka). Çekim anındaki görüntünün çerçevesi kırmızı olur.
- **Görüntüye tıkla:** tespit sayıları, düşük güvenli tespitler ve bağlandıkları track, karede olup tespit edilmeyen track'ler.
- **Araca ya da track'e tıkla:** 2 saatlik rota, 15 dakikalık aralıklarla üsse mesafe ve hız.
- **Adres çubuğuna kısayol:** `index.html#img_000860` ya da `index.html#T0122` doğrudan o görüntüye/track'e gider.
- **"Sadece yaklaşanlar" filtresi:** B7'yi gözle görmek için.

Bakmanızı önerdiğim üç şey:
1. `#img_000860`: kamyonun 0,10 güvenle bulunduğu ve T0122 ile eşleştiği kare.
2. `#T0122`: bekleme → ani kalkış → koridor değişimi.
3. Kaydırıcıyı 13:40'a getirip sağdaki (Kuzeydoğu) "park halinde" raporuna bakın: B8'deki zaman kayması örneği.

# Drone Araç Tespiti — Car/Van Classifier

Roketsan "Level Up AI" hackathonu verisinde (drone görüntüleri, sınıflar: car, van, truck, bus) YOLO11s dedektörünün en çok karıştırdığı iki sınıfı (car ↔ van) ayırmak için ikinci aşama bir sınıflandırıcı.

Tüm adımlar Colab notebook'u `yolo11s_baseline.ipynb` içinde, notebook'un sonuna eklenen hücrelerde yapılır.

## Veri

| Yol | İçerik |
|---|---|
| `MyDrive/level-up-ai-roketsan-yapay-zeka-hackathonu/train/images` | 6472 train görüntüsü |
| `MyDrive/level-up-ai-roketsan-yapay-zeka-hackathonu/train/annotations.csv` | `image_id, x, y, w, h, label` (sol-üst köşe + genişlik/yükseklik, piksel) |

Train'deki kutu dağılımı: car 124.843 · van 22.787 · truck 12.109 · bus 5.610.
Kutular küçük: alan medyanı ~1568 px² (≈ 40×40 px).

## Başlangıç noktası: YOLO11s dedektör

`imgsz=1024`, 40 epoch, A100. Val sonuçları (mAP@0.5):

| all | car | van | truck | bus |
|---|---|---|---|---|
| 0.762 | 0.887 | **0.691** | 0.678 | 0.794 |

Van, dedektörün en zayıf sınıflarından biri ve hatalarının büyük kısmı car ile karışma. Bu yüzden car/van ayrımı için ayrı bir classifier denendi.

Model: `MyDrive/yolo_outputs/runs/yolo11s_base/weights/best.pt`

## Aşama 1 — Car/van kutularını kırpma (padding'siz)

- `annotations.csv`'den sadece `car` ve `van` satırları alınır.
- Her kutu görüntü sınırlarına kırpılır, kenarı 2 px'den küçük olanlar atlanır, JPEG (quality=95) olarak kaydedilir.
- Dosya adı: `{image_id}_{annotation satır index'i}.jpg`.
- Kırpmalar önce Colab diskine (`/content/crops_car_van`) yazılır, sonra tek zip olarak Drive'a kopyalanır. ~147 bin küçük dosyayı tek tek Drive'a yazmak çok yavaş.

**Çıktı:** `MyDrive/classifier_data/crops_car_van.zip`

```
car/*.jpg          # 124.843 adet
van/*.jpg          #  22.787 adet
crops.csv          # file, image_id, label, x, y, w, h
```

`crops.csv` içindeki `image_id`, train/val ayrımını görüntü bazında yapmak için tutulur (aşağıya bakın).

## Aşama 2 — YOLO11s-cls eğitimi

**Veri hazırlığı** (`/content/cls_data/{train,val}/{car,van}`, symlink):

- **Görüntü bazında split:** `image_id`'ler karıştırılıp %10'u val'e ayrılır (seed 42). Aynı fotoğraftan çıkan kırpmalar hep aynı tarafta kalır. Kırpma bazında rastgele bölmek, aynı sahnenin komşu araçlarının hem train hem val'e düşmesine ve val skorunun şişmesine yol açardı.
- **Van oversampling:** Van, car'dan ~5.5 kat az. Train'de her van kırpması 3 kez (farklı adlı symlink ile) yer alır. Val'e dokunulmaz.
- Sonuç: train 172.666 görüntü. Ultralytics, 287 çok küçük kırpmayı (kenarı < 10 px) "corrupt" sayıp atlar.

**Eğitim:** `yolo11s-cls.pt`, `imgsz=128`, `epochs=30`, `batch=256`, `patience=10`, seed 42.

**Çıktı:** `MyDrive/classifier_data/runs/yolo11s_cls_car_van/` (`weights/best.pt`, `results.csv`, confusion matrix'ler)

### Sonuç

Early stopping ile 17. epoch'ta durdu; en iyi val top-1 **0.904** (epoch 7).

Normalize confusion matrix (sütun = gerçek sınıf):

| Tahmin \ Gerçek | car | van |
|---|---|---|
| car | **0.95** | 0.34 |
| van | 0.05 | **0.66** |

- Van'ların üçte biri car olarak sınıflanıyor (van recall 0.66).
- Val'in ~%85'i car olduğu için "hepsine car de" bile ~0.85 top-1 verir. 0.904 bunun yalnızca biraz üstünde.
- Dedektörün kendi van AP50'si (0.691) düşünülünce bu classifier henüz net bir katkı sağlamıyor.

**Olası sebep:** Kırpmalar çok küçük ve sadece aracın kendisini içeriyor. Yukarıdan bakınca car/van ayrımını en çok belirleyen boyut ve oran bilgisi, 128×128'e yeniden boyutlandırınca kayboluyor. Çevredeki bağlam da (yol, komşu araçlar) hiç yok.

## Aşama 3 — Padding'li yeniden kırpma

Kutular her kenardan kutu boyutunun %20'si kadar genişletilerek yeniden kırpılır:

```
pad_x = 0.20 * w,  pad_y = 0.20 * h
x1 = max(0, x - pad_x),      y1 = max(0, y - pad_y)
x2 = min(W, x + w + pad_x),  y2 = min(H, y + h + pad_y)
```

Böylece aracın etrafındaki bağlam ve komşu araçlarla göreli boyut bilgisi kırpmaya girer. Genişletme kutunun kendi boyutuyla orantılı olduğu için küçük ve büyük araçlara aynı oranda bağlam eklenir.

Klasör yapısı ve `crops.csv` formatı Aşama 1 ile aynıdır. `crops.csv`'de ek olarak orijinal (padding'siz) kutu da tutulur.

**Çıktı:** `MyDrive/classifier_data/crops_car_van_pad20.zip`

```
car/*.jpg          # 124.843 adet
van/*.jpg          #  22.787 adet
crops.csv          # file, image_id, label, x, y, w, h (padding'li kutu), ox, oy, ow, oh (orijinal kutu)
```

Dosya adları padding'siz setle aynıdır (`{image_id}_{satır index'i}.jpg`), yani iki set birebir eşleşir.

Kenarı 10 px altında kalan kırpma sayısı 287'den **11**'e düştü. Böylece Ultralytics'in "corrupt" diye attığı örneklerin neredeyse tamamı artık eğitime girebiliyor.

Padding'siz zip (`crops_car_van.zip`) karşılaştırma için olduğu gibi bırakıldı.

## Aşama 4 — Padding'li kırpmalarla YOLO11s-cls eğitimi

Aşama 2 ile birebir aynı kurulum. Tek fark kırpmaların padding'li olması:

- **Aynı split:** Aynı `image_id` listesi, seed 42, %10 val. train car 111.538 / van 61.128 (3x oversample), val car 13.305 / van 2.411.
- **Aynı ayarlar:** `yolo11s-cls.pt`, `imgsz=128`, `epochs=30`, `batch=256`, `patience=10`.
- **Farklı çalıştırma şekli:** Eğitim `!yolo classify train ... > /content/train_pad20.log` ile başlatıldı. Aşama 2'deki gibi notebook içinde çalıştırınca uzun eğitim çıktısı Colab sekmesini donduruyordu.

**Çıktı:** `MyDrive/classifier_data/runs/yolo11s_cls_car_van_pad20/` (`weights/best.pt`, `results.csv`, confusion matrix'ler)

### Sonuç

Early stopping tetiklenmedi, 30 epoch'un tamamı koştu. Val top-1 son epoch'lara kadar yükselmeye devam etti.

Val confusion matrix (sayılar, sütun = gerçek sınıf):

| Tahmin \ Gerçek | car | van |
|---|---|---|
| car | 12.618 | 575 |
| van | 685 | 1.836 |

### Padding'siz ↔ padding'li karşılaştırma

| Metrik | Padding'siz (Aşama 2) | Padding'li (Aşama 4) |
|---|---|---|
| Val top-1 (best) | 0.904 | **0.920** |
| En düşük val loss | 0.260 | **0.243** |
| car recall | 0.95 | 0.95 |
| **van recall** | 0.66 | **0.76** |
| van precision | ~0.70 | 0.73 |
| Eğitim | epoch 17'de early stopping | 30 epoch, hâlâ iyileşiyordu |

- %20 bağlam eklemek van recall'unu **+10 puan** artırdı. Car doğruluğu hiç düşmedi. Kırpmalara bağlam eklemenin car/van ayrımında önemli olduğu doğrulandı.
- Van'ların hâlâ ~%24'ü car olarak sınıflanıyor.
- Model 30. epoch'ta hâlâ iyileşiyordu, yani daha uzun eğitim ek kazanç sağlayabilir.

**Model kopyası:** `MyDrive/classifier_data/models/yolo11s_cls_pad20_vanrecall076.pt`. Sonraki eğitimler `runs/` altındaki dosyanın üzerine yazsa bile bu referans model korunur.

## Aşama 5 — Veri analizi: şüpheli etiketler ve kutu boyutu

### Şüpheli etiketler

Padding'li model bütün kırpmalar üzerinde çalıştırıldı. Modelin etikete %90'ın üzerinde güvenle itiraz ettiği train örnekleri işaretlendi:

| | Temiz | Şüpheli etiket | Kısa kenar < 10 px |
|---|---|---|---|
| car | 110.178 | 959 | 401 |
| van | 20.119 | 243 | 14 |

- **Kırpma kodu doğrulandı:** 1.204 şüpheli örneğin hepsi `annotations.csv`'deki satırla birebir eşleşiyor. Çelişki kırpma kodundan kaynaklanmıyor.
- **Etiketler değiştirilmedi.** Birkaç örnek gözle incelendiğinde asıl sorunun netlik/çözünürlük olduğu düşünüldü.

**Çıktılar** (`MyDrive/classifier_data/pad20_clean/`):
- `crops_scored.csv`: her kırpmanın model skoru (`p_van`) ve split bilgisi
- `suspicious_all.csv`: şüpheli örneklerin tam listesi, `annotations.csv` satır index'iyle
- `examples/`: şüpheli kutular, orijinal görüntü üzerine kırmızıyla çizilmiş hâlde
- `review_*.jpg`: şüpheli kırpmaların ızgara görselleri

### Boyuta göre ayırt edilebilirlik (val, padding'li model)

| Kısa kenar (px) | car / van (val) | car doğruluğu | van doğruluğu | Val'in %'si |
|---|---|---|---|---|
| < 10 | 73 / 4 | 0.92 | 0.00 | 0.5 |
| 10–15 | 1114 / 141 | 0.94 | 0.69 | 8.0 |
| 15–20 | 1923 / 321 | 0.93 | 0.71 | 14.3 |
| 20–25 | 1723 / 278 | 0.95 | 0.75 | 12.7 |
| 25–30 | 1401 / 242 | 0.94 | 0.80 | 10.5 |
| 30–40 | 2143 / 396 | 0.95 | 0.78 | 16.2 |
| 40–60 | 2306 / 470 | 0.96 | 0.72 | 17.7 |
| 60+ | 2622 / 559 | 0.96 | 0.83 | 20.2 |

- **Keskin bir eşik yok.** Küçük van'lar (0.69–0.71) büyüklerden (0.72–0.83) sadece ~10 puan daha kötü.
- **Büyük van'lar da zorlanıyor** (40–60 px: 0.72). Sorun yalnızca çözünürlük değil.
- **Olası sebep:** Ultralytics'in sınıflandırma ön işlemesi. Kareye getirirken ortadan kırpıyor, bu uzun araçların uçlarını kesiyor. Buna ek olarak agresif augmentasyon var: `scale=0.5`, `erasing=0.4`, randaugment.
- **Karar:** Sadece kısa kenarı 10 px'in altındaki kutular (~%0.5) atılır. Daha fazlasını atmanın faydası küçük, üstelik test'te bu kutular yine gelecek.

Görsel: `pad20_clean/size_buckets_van_left_car_right.jpg`. Her satır bir boyut grubu, solda van, sağda car.

## Aşama 6 — Kareli bağlam kırpması

Her car/van kutusu için kare bir kırpma alınır:
- Kenar = 2 × kutunun uzun kenarı, araç ortada.
- Görüntü dışına taşan kısım gri (114) ile doldurulur.
- Orijinal çözünürlükte kaydedilir; boyutlandırma eğitimde yapılır.
- Kısa kenarı < 10 px olan kutular atılır.

Ortadan kırpma olmadığı için araç hiç kesilmez, en-boy oranı korunur ve komşu araçlar bağlam olarak görünür.

**Çıktı:** `MyDrive/classifier_data/crops_car_van_sq2.zip` (car 124.369, van 22.769)

`crops.csv` kolonları:

| Kolon | Anlamı |
|---|---|
| `ox, oy, ow, oh` | orijinal kutu |
| `x0, y0, side` | karenin görüntüdeki yeri; kutunun kare içindeki yeri = (`ox - x0`, `oy - y0`) |
| `img_w, img_h` | görüntü boyutu |
| `med_car_area` | aynı görüntüdeki car kutularının medyan alanı |

## Aşama 7 — timm tabanlı classifier (`train_cls.py`)

Ultralytics yerine özel bir eğitim scripti: `MyDrive/classifier_data/train_cls.py`. Kaynak kod: bu README ile aynı klasörde.

**Model:**
- `convnext_tiny.fb_in22k_ft_in1k` (ImageNet ön eğitimli), 224×224 girdi.
- Opsiyonel `--use_mask`: 4. kanal olarak hedef kutunun maskesi. Kırpmada komşu araçlar da olduğu için model hangisine bakacağını bilir.
- Opsiyonel `--use_size`: 3 boyut özelliği küçük bir MLP'den geçip görsel özelliklerle birleştirilir:
  - `log(uzun/kısa kenar)`: yönden bağımsız en-boy oranı
  - `log(alan / aynı görüntüdeki medyan car alanı)`: drone yüksekliğinden bağımsız göreli boyut
  - `log(alan / görüntü alanı)`

**Eğitim:**
- **Val:** Önceki eğitimlerle aynı. Split `crops_scored.csv`'den okunur.
- **Denge:** Her epoch tüm van'lar ~1 kez ve 2 katı kadar rastgele car görülür (`WeightedRandomSampler`). Kopyalama yok.
- **Augmentasyon:**
  - Kullanılan: 90°'lik döndürmeler ve yatay çevirme (yukarıdan çekimde yön anlamsız), rastgele küçültüp geri büyütme (düşük çözünürlüğe dayanıklılık, p=0.3), hafif parlaklık/kontrast.
  - Kullanılmayan: rastgele silme ve agresif kırpma.
- **Optimizasyon:** Cross-entropy (label smoothing 0.1), AdamW (lr 2e-4, wd 0.05), 1 epoch warmup ve cosine, EMA (0.999), bf16, 25 epoch.
- **Model seçimi:** En iyi epoch val **van F1**'e göre seçilir. Sonunda TTA'sız ve 8 yönlü TTA'lı değerlendirme yapılır.

**Çıktılar** (`--out` klasörü):
- `best.pt`
- `results.csv`: epoch başına top1, car/van recall, van precision/F1
- `final_metrics.json`
- `val_predictions.csv`

**Çalıştırma** (Colab, arka planda):

```
!pip -q install timm
!nohup python /content/drive/MyDrive/classifier_data/train_cls.py \
    --data /content/crops_car_van_sq2 \
    --zip /content/drive/MyDrive/classifier_data/crops_car_van_sq2.zip \
    --split_csv /content/drive/MyDrive/classifier_data/pad20_clean/crops_scored.csv \
    --out /content/drive/MyDrive/classifier_data/runs/convnext_sq2_a > /content/train_a.log 2>&1 &
```

### Deneyler (hepsi aynı val setinde)

| Deney | Ayarlar | Çıktı klasörü | Durum |
|---|---|---|---|
| 7a | kareli kırpma + ConvNeXt-Tiny | `runs/convnext_sq2_a` | 10. epoch'ta durduruldu; ViT-L'ye geçildi |
| 7c | kareli kırpma + DINOv2 ViT-L/14 (ilk deneme) | `runs/vitl_dinov2_sq2` | Colab oturumu 12/15 epoch'ta kapandı |
| **7d** | **7c'nin aynısı, baştan 15 epoch** | **`runs/vitl_dinov2_sq2_v2`** | **tamamlandı: en iyi model** |

**7c/7d ViT-L ayarları:**
- Model: `vit_large_patch14_dinov2.lvd142m` (303M parametre), 224 girdi.
- Eğitim: 15 epoch, batch 64.
- Optimizasyon:
  - lr 2e-4
  - katman bazlı lr azaltma 0.85
  - 2 epoch warmup
  - drop path 0.2
  - weight decay 0.05
  - gradient clipping 1.0
  - EMA 0.9995
- Süre: epoch başına ~5 dk (A100), GPU'da ~23.5 GB.

Script her epoch sonunda `last.pt` yazar. Colab oturumu koparsa aynı komut `--resume` ile kaldığı epoch'tan devam eder. `last.pt` eğitim bitince silinir.

### Sonuç: ViT-L (7d)

En iyi epoch 15. Val sonuçları, 0.5 eşikle:

| Metrik | TTA'sız | **8 yönlü TTA** |
|---|---|---|
| top-1 | 0.930 | **0.934** |
| car recall | 0.955 | 0.959 |
| van recall | 0.795 | **0.800** |
| van precision | 0.761 | **0.779** |
| van F1 | 0.778 | **0.789** |

Confusion matrix (TTA'lı, sayılar):

| Gerçek \ Tahmin | car | van |
|---|---|---|
| car (13.232) | 12.685 | 547 |
| van (2.407) | 481 | 1.926 |

### Tüm classifier'ların karşılaştırması

| Model | van recall | van precision | van F1 | top-1 |
|---|---|---|---|---|
| YOLO11s-cls, padding'siz (Aşama 2) | 0.66 | ~0.70 | ~0.68 | 0.904 |
| YOLO11s-cls, %20 padding (Aşama 4) | 0.76 | 0.73 | ~0.745 | 0.920 |
| ConvNeXt-Tiny, kareli (7a, 10. epoch) | 0.77 | 0.76 | 0.765 | 0.927 |
| **ViT-L DINOv2, kareli (7d) + TTA** | **0.80** | **0.78** | **0.789** | **0.934** |

- ViT-L, %20 padding'li YOLO modeline göre van F1'i **+4.4 puan** artırdı. Van'larda hem recall hem precision iyileşti.
- İki ayrı ViT-L eğitimi (7c, 7d) aynı seviyeye ulaştı. Sonuç tekrarlanabilir.
- 10. epoch'tan sonra kazanç küçük (0.776 → 0.778). Model bu kurulumda doymaya yakın.

**Model:**
- Drive: `MyDrive/classifier_data/runs/vitl_dinov2_sq2_v2/best.pt` (1.2 GB)
- İçerik: EMA ağırlıkları, eğitim argümanları, sınıf listesi, boyut özelliği normalizasyonu.

`val_predictions.csv` her val kırpması için TTA'lı `p_van` değerini içerir. Karar eşiği ayarı için kullanılabilir.

## Sonraki adımlar

1. **ViT-L + boyut özellikleri ve maske kanalı:** `--use_size --use_mask`. Büyük van'ların car'la karışmasına karşı göreli boyut bilgisi.
2. **Van karar eşiği:** Van için eşiği val'de ayarlamak (0.5 yerine ~0.3–0.4). Yeniden eğitim gerektirmez.
3. **Dedektöre entegrasyon:** Dedektörün car/van tahminlerini kareli kırpıp classifier ile yeniden etiketlemek ve val mAP@0.5'e etkisini ölçmek. Asıl hedef metrik bu. Çok küçük kutularda dedektörün kendi etiketi korunabilir.

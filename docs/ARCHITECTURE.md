# LLM / Agent Katmanı — Mimari ve Veri Sözleşmeleri

## 1. Genel akış

```mermaid
flowchart TB
  subgraph K1["Kod katmanı (ekip)"]
    DET["Tespit<br/>raw_dets: label, conf, lat, lon"]
    GEO["Geo + track eşleştirme"]
    MOT["Hareket özeti"]
  end
  subgraph K2["Kanıt paketi (builder.py)"]
    ASSOC["Rapor ↔ görüntü ilişkilendirme<br/>≤250 m, çekimden önceki 120 dk"]
    CHK["Objektif rapor kontrolleri"]
    FLG["Sert bayraklar → rule_floor"]
    PACK[["EvidencePack JSON<br/>~3K token"]]
  end
  subgraph K3["Karar döngüsü (LLM)"]
    LLM["GLM-5.3-Flash<br/>reasoning_effort=high"]
    VIS["inspect_vehicle<br/>(kırpılmış görüntü, vision)"]
    SUB["submit_assessment"]
  end
  VAL{"validator.py"}
  OUT[["Decision JSON → cache → UI / brief"]]

  DET --> GEO --> MOT --> PACK
  ASSOC --> CHK --> PACK
  FLG --> PACK
  PACK --> LLM
  LLM <-->|gerekirse| VIS
  LLM --> SUB --> VAL
  VAL -->|hata listesi, en fazla 1 tekrar| LLM
  VAL -->|geçerli| OUT
```

**İlke:** Kod ölçer, LLM yorumlar ve karar verir, kod denetler.

## 2. Karar döngüsü (görüntü başına)

```mermaid
sequenceDiagram
  participant P as Pipeline
  participant L as GLM
  participant T as Tool'lar
  participant V as Validator
  P->>L: system prompt + EvidencePack
  opt Görsel iddia veya belirsiz sınıf
    L->>T: inspect_vehicle(D3, "kasası dolu mu?")
    T-->>L: "Kasa branda ile örtülü"
  end
  L->>T: submit_assessment(Decision)
  T->>V: validate(decision, pack)
  alt Hata var
    V-->>L: tool sonucu olarak hata listesi
    L->>T: düzeltilmiş submit_assessment
  end
  V-->>P: kabul edilen karar (cache'e yazılır)
```

Döngü üst sınırı 6 adım. İkinci denemede de hata kalırsa karar `confidence="dusuk"` ile ve hatalar notlanarak kaydedilir; seviye en az `rule_floor` olur.

## 3. Dosyalar

| Dosya | Sorumluluk |
|---|---|
| `dss/schemas.py` | `EvidencePack` ve `Decision` sözleşmeleri, kimlik kuralları |
| `dss/evidence/builder.py` | Ham veri + tespitler → `EvidencePack` |
| `dss/agent/validator.py` | Karar denetimi: alt sınır, eksik hüküm, uydurma kimlik, dost-iddia politikası |
| `dss/agent/tools.py` | `submit_assessment`, `inspect_vehicle`, sohbet tool'ları ($ref'siz şema) |
| `eval/examples/example_evidence_pack.json` | img_003839 için gerçek veriden üretilmiş örnek paket |
| `eval/examples/example_decision.json` | Validator'dan geçen örnek karar |
| *(sıradaki)* `llm_client.py` | OpenAI SDK, semaphore(4), retry, cache, bütçe koruması |
| *(sıradaki)* `prompts.py` | System prompt: güven hiyerarşisi, kategori tanımları, örnek |
| *(sıradaki)* `decide.py` / `chat.py` | Karar döngüsü ve sohbet döngüsü |

## 4. Ekip arayüzü

Ekipten beklenen tek girdi, görüntü başına tespit listesi:

```python
raw_dets = [{"label": "truck", "conf": 0.91, "lat": 39.93742, "lon": 32.84829}, ...]
pack = build_pack(Data("data/"), "img_003839", raw_dets)
```

`builder.py` içindeki `Data.xy`, `motion` ve eşleştirme kısımları geçici. Geo/track modülü hazır olunca aynı imzayla onun fonksiyonları çağrılacak.

## 5. Kimlikler

| Önek | Anlamı | Örnek |
|---|---|---|
| `D` | Görüntüdeki tespit | `D3` |
| `T` | tracks.csv track_id | `T0182` |
| `R` | Rapor (field_reports.json sırası, 1'den) | `R001` |
| `F` | Kodun ürettiği sert bayrak | `F2` |

## 6. Politikalar (validator'da kodlu)

1. `attention_level` ≥ `rule_floor`. Daha yüksekse `deviation_from_rules` zorunlu.
2. `reports` listesindeki her rapora bir hüküm verilir; `context_reports` opsiyonel.
3. Karar yalnızca pakette var olan kimliklere atıf yapabilir.
4. `dost_kimlik` kategorisinde hüküm `DOGRULANDI` değilse `risk_effect` "azaltir" olamaz.
5. `DOGRULANDI` / `KISMEN_DOGRULANDI` / `CELISIYOR` hükümleri kanıt atfı olmadan verilemez.

## 7. Sert bayraklar (kalibre edilecek)

| Kod | Koşul | min_level |
|---|---|---|
| `YAKIN_VARIS` | ETA < 10 dk | KRITIK |
| `YAKIN_YAKLASMA` | Üsse < 1,5 km ve son 30 dk yaklaşma > 1 m/s | YUKSEK |
| `AGIR_ARAC_YAKIN` | truck/bus, üsse < 3 km | ORTA |
| `UZUN_BEKLEME_YAKIN` | Üsse 2 km içinde ≥ 30 dk duraklama | ORTA |
| `IZSIZ_AGIR_ARAC` | Track'i olmayan truck/bus, üsse < 3 km | ORTA |

## 8. Rapor kategorileri (`Decision.report_verdicts.category`)

`gorulme`, `hareketsizlik`, `hareket_yonu`, `dost_kimlik`, `bolge_olumsuz`, `olagan_yogunluk`, `gorsel_nitelik`, `gurultu`

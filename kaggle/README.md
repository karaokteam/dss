# kaggle/ — Aşama 1 (Araç Tespiti) · Step: DET-1

- `notebooks/` — eğitim / çıkarım notebook'ları; final notebook Coderspace ve ROKETSAN ile paylaşılır (OI-DET-2).
- `submissions/` — (gitignore) üretilen CSV'ler. Format: `image_id,PredictionString`, tahmin yoksa `none`.
- Eğitilen ağırlık → `models/best.pt` (git dışı). Agent `agent/detection/detector.py` üzerinden kullanır.

Hatırlatma: 4 sınıf (car, van, truck, bus) · mAP@0.5 · 200 px² altı etiketsiz · günlük 5 / toplam 10 gönderim.

"""split_val mAP@0.5 and end-to-end speed of an engine or checkpoint. Appends to results/results.json.

    python evaluate.py tensorrt fp16 work/engines/yolo26l_1920_split_fp16.engine
    python evaluate.py pytorch fp32 work/weights/split/yolo26l_1920_split.pt

End-to-end = reading the JPEG, resizing, the model and multi-label NMS (confidence >= 0.005, as in phase 1).
"""
import functools
import json
import sys
import time
from pathlib import Path

from ultralytics import YOLO
from ultralytics.utils import nms

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'phase1_train'))
from roketsan import imagesets, metric  # noqa: E402

RESULTS = Path(__file__).parent / 'results' / 'results.json'

backend, precision, model_file = sys.argv[1], sys.argv[2], sys.argv[3]
nms.non_max_suppression = functools.partial(nms.non_max_suppression, multi_label=True)
model = YOLO(model_file, task='detect')
ids, files = imagesets.load('split_val')

predictions = {}
start = time.time()
for i in range(0, len(ids), 16):
    batch = ids[i:i + 16]
    results = model.predict([str(files[image_id]) for image_id in batch], imgsz=1920, conf=0.005, iou=0.7,
                            max_det=1000, batch=16, half=(backend == 'pytorch' and precision == 'fp16'), verbose=False)
    for image_id, r in zip(batch, results):
        parts = []
        for (x1, y1, x2, y2), score, c in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
            parts.append(f'{model.names[int(c)]} {score:.4f} {round(x1)} {round(y1)} {round(x2 - x1)} {round(y2 - y1)}')
        predictions[image_id] = ' '.join(parts) or 'none'
seconds = time.time() - start

mean_ap, per_class = metric.score(metric.load_benchmark('split_val'), predictions)
row = {'backend': 'TensorRT' if backend == 'tensorrt' else 'PyTorch', 'precision': precision,
       'map50': 100 * mean_ap, 'per_class': {k: 100 * v for k, v in per_class.items()},
       'end_to_end_img_per_s': len(ids) / seconds}
print(f'mAP@0.5 {row["map50"]:.2f}   {row["end_to_end_img_per_s"]:.0f} images/s end to end')

results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {'latency': [], 'accuracy': []}
results['accuracy'].append(row)
RESULTS.parent.mkdir(exist_ok=True)
RESULTS.write_text(json.dumps(results, indent=1))

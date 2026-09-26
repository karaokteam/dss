"""Send JPEGs to the Triton server from several clients at once and measure throughput and latency.

    python load_test.py IMAGE_FOLDER --label "2 instances, batching" --concurrency 1 2 4 8 16 32

Each client sends one image per request and waits for the answer (like a camera stream). Results are appended
to results/triton.json, including the average batch size Triton formed.
"""
import argparse
import json
import threading
import time
from pathlib import Path

import numpy as np
from tritonclient.grpc import InferenceServerClient, InferInput

MODEL = 'yolo26l'
RESULTS = Path(__file__).parent / 'results' / 'triton.json'


def client_loop(jpegs, stop, latencies, errors, offset):
    client = InferenceServerClient('localhost:8001')
    i = offset
    while not stop.is_set():
        jpeg = np.frombuffer(jpegs[i % len(jpegs)], dtype=np.uint8)[None]   # one JPEG file as [1, size] bytes
        request = InferInput('image', list(jpeg.shape), 'UINT8')
        request.set_data_from_numpy(jpeg)
        start = time.perf_counter()
        try:
            client.infer(MODEL, [request])
            latencies.append(time.perf_counter() - start)
        except Exception:   # e.g. the server ran out of GPU memory: count it and keep going
            errors.append(1)
        i += 1


def batch_counts(client):
    """Total images and total model executions so far (their ratio is the average batch size)."""
    stats = client.get_inference_statistics(MODEL, as_json=True)['model_stats'][0]
    return int(stats.get('inference_count', 0)), int(stats.get('execution_count', 0))


def run(jpegs, concurrency, seconds):
    stop, latencies, errors, threads = threading.Event(), [], [], []
    for c in range(concurrency):
        threads.append(threading.Thread(target=client_loop, args=(jpegs, stop, latencies, errors, c * 7)))
        threads[-1].start()
    time.sleep(3)                                   # warm-up
    latencies.clear()
    errors.clear()
    admin = InferenceServerClient('localhost:8001')
    images_before, runs_before = batch_counts(admin)
    start = time.perf_counter()
    time.sleep(seconds)
    measured = list(latencies)
    failed = len(errors)
    elapsed = time.perf_counter() - start
    images_after, runs_after = batch_counts(admin)
    stop.set()
    for t in threads:
        t.join()
    ms = np.array(measured) * 1000
    return {'concurrency': concurrency, 'img_per_s': len(measured) / elapsed,
            'p50_ms': float(np.percentile(ms, 50)), 'p95_ms': float(np.percentile(ms, 95)),
            'p99_ms': float(np.percentile(ms, 99)), 'failed': failed,
            'avg_batch': (images_after - images_before) / max(runs_after - runs_before, 1)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('images')
    parser.add_argument('--label', required=True)
    parser.add_argument('--concurrency', type=int, nargs='+', default=[1, 2, 4, 8, 16, 32])
    parser.add_argument('--seconds', type=float, default=15)
    args = parser.parse_args()

    jpegs = [p.read_bytes() for p in sorted(Path(args.images).glob('*.jpg'))[:64]]
    rows = json.loads(RESULTS.read_text()) if RESULTS.exists() else []
    rows = [r for r in rows if r['label'] != args.label]   # a re-run replaces the old numbers
    for concurrency in args.concurrency:
        row = {'label': args.label, **run(jpegs, concurrency, args.seconds)}
        rows.append(row)
        print(f'{args.label:28s} clients {concurrency:2d}: {row["img_per_s"]:6.1f} img/s  p50 {row["p50_ms"]:6.1f} ms  '
              f'p95 {row["p95_ms"]:6.1f} ms  batch {row["avg_batch"]:.1f}  failed {row["failed"]}', flush=True)
        RESULTS.parent.mkdir(exist_ok=True)
        RESULTS.write_text(json.dumps(rows, indent=1))

"""Run the 22 inference passes of configs/pipeline.yaml.   python scripts/10_run_passes.py test

split_val uses the split-trained models, anything else the full-data models. Existing pass files are skipped.
YOLO and RF-DETR need different environments: set YOLO_PY and RFDETR_PY.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roketsan import config, imagesets  # noqa: E402

images = sys.argv[1]
cfg = config.load()
variant = 'split' if images == 'split_val' else 'full'
out_dir = imagesets.output_dir(images) / 'passes'
scripts = Path(__file__).parent

for p in cfg['passes']:
    out = out_dir / f'{p["id"]:02d}.csv'
    if out.exists():
        continue
    if cfg['models'][p['model']]['type'] == 'yolo':
        command = [os.environ.get('YOLO_PY', 'python'), scripts / 'predict_yolo_pass.py']
    else:
        command = [os.environ.get('RFDETR_PY', 'python'), scripts / 'predict_rfdetr_pass.py']
    command += ['--weights', config.weight_file(cfg, p['model'], variant), '--images', images,
                '--size', str(p['size']), '--out', out]
    if p['hflip']:
        command.append('--hflip')
    if p['vflip']:
        command.append('--vflip')
    if p.get('half'):
        command.append('--half')

    print(f'pass {p["id"]}: {p["model"]} at {p["size"]} px')
    subprocess.run([str(c) for c in command], check=True)

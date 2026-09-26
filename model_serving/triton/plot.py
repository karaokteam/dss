"""results/triton.json -> results/triton_summary.png and results/triton_table.md"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator

FOLDER = Path(__file__).parent / 'results'
rows = json.loads((FOLDER / 'triton.json').read_text())

plt.rcParams.update({
    'font.family': 'Helvetica', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#888888', 'axes.labelcolor': '#333333', 'xtick.color': '#555555', 'ytick.color': '#555555',
    'axes.grid': True, 'axes.grid.axis': 'y', 'grid.color': '#e6e6e6', 'figure.dpi': 200,
    'savefig.bbox': 'tight', 'legend.frameon': False,
})
COLOR = {'1': '#9a9a9a', '2': '#2f6fdf', '4': '#e8833a'}   # by instance count
labels = list(dict.fromkeys(r['label'] for r in rows))
clients = sorted({r['concurrency'] for r in rows})


def curve(label, key):
    points = sorted((r['concurrency'], r[key]) for r in rows if r['label'] == label)
    return [p[0] for p in points], [p[1] for p in points]


def draw(ax, key, ylabel, only_batching=False):
    for label in labels:
        instances = label.split()[0]
        batching = label.endswith('on')
        if only_batching and not batching:
            continue
        x, y = curve(label, key)
        ax.plot(x, y, marker='o' if batching else None, ms=3.5, lw=1.8 if batching else 1.2,
                ls='-' if batching else '--', color=COLOR[instances], label=label)
        # points where requests failed (e.g. out of GPU memory) are marked with a red cross
        for r in rows:
            if r['label'] == label and r.get('failed', 0) > 0:
                ax.scatter(r['concurrency'], r[key], marker='x', s=40, color='#d62728', zorder=4)
    ax.set_xscale('log', base=2)
    ax.xaxis.set_major_locator(FixedLocator(clients))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([str(c) for c in clients])
    ax.set_xlabel('concurrent clients')
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)


fig, axes = plt.subplots(1, 3, figsize=(14, 3.6), gridspec_kw={'wspace': 0.3})
draw(axes[0], 'img_per_s', 'images / s')
draw(axes[1], 'p95_ms', 'p95 latency (ms)')
draw(axes[2], 'avg_batch', 'images per model run', only_batching=True)
for ax, title in zip(axes, ['Throughput', 'Latency (95th percentile)', 'Batch size formed by Triton']):
    ax.set_title(title, loc='left', fontsize=10.5)
axes[0].legend(fontsize=7.5, loc='upper left')
fig.suptitle('YOLO26-L TensorRT fp16 on Triton, one H200 (JPEG in, boxes out)', x=0.125, ha='left', fontsize=11.5, y=1.03)
fig.savefig(FOLDER / 'triton_summary.png')

lines = ['| Setup | ' + ' | '.join(f'{c} client{"s" * (c > 1)}' for c in clients) + ' |', '|---|' + '---|' * len(clients)]
for label in labels:
    cells = []
    for c in clients:
        r = next(r for r in rows if r['label'] == label and r['concurrency'] == c)
        failed = f', {r["failed"]} failed' if r.get('failed', 0) else ''
        cells.append(f'{r["img_per_s"]:.0f} img/s, p95 {r["p95_ms"]:.0f} ms{failed}')
    lines.append(f'| {label} | ' + ' | '.join(cells) + ' |')
(FOLDER / 'triton_table.md').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))

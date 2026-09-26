"""results/results.json -> results/{latency,throughput,speed_vs_accuracy,summary}.png and table.md"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator

FOLDER = Path(__file__).parent / 'results'
results = json.loads((FOLDER / 'results.json').read_text())

plt.rcParams.update({
    'font.family': 'Helvetica', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#888888', 'axes.labelcolor': '#333333', 'xtick.color': '#555555', 'ytick.color': '#555555',
    'axes.grid': True, 'axes.grid.axis': 'y', 'grid.color': '#e6e6e6', 'figure.dpi': 200,
    'savefig.bbox': 'tight', 'legend.frameon': False,
})
COLOR = {'fp32': '#9a9a9a', 'fp16': '#2f6fdf', 'int8': '#e8833a'}
BATCHES = sorted({r['batch'] for r in results['latency']})


def curve(backend, precision, key):
    rows = sorted((r for r in results['latency'] if r['backend'] == backend and r['precision'] == precision),
                  key=lambda r: r['batch'])
    return [r['batch'] for r in rows], [r[key] for r in rows]


def plot_by_batch(ax, key, ylabel):
    for precision in COLOR:
        x, y = curve('TensorRT', precision, key)
        if x:
            ax.plot(x, y, marker='o', ms=4, lw=1.8, color=COLOR[precision], label=f'TensorRT {precision}')
            ax.annotate(f'{y[-1]:.0f}', (x[-1], y[-1]), xytext=(5, 0), textcoords='offset points', va='center',
                        color=COLOR[precision], fontsize=8.5)
        x, y = curve('PyTorch', precision, key)
        if x:
            ax.plot(x, y, ls='--', lw=1.2, color=COLOR[precision], alpha=0.7, label=f'PyTorch {precision}')
    ax.set_xscale('log', base=2)
    ax.xaxis.set_major_locator(FixedLocator(BATCHES))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([str(b) for b in BATCHES])
    ax.set_xlabel('batch size')
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)


# where each point's label goes, so close points don't collide: (x offset, y offset, alignment)
LABEL_PLACE = {('PyTorch', 'fp32'): (-6, 10, 'right'), ('PyTorch', 'fp16'): (6, 10, 'left')}


def plot_speed_vs_accuracy(ax):
    speed = {(r['backend'], r['precision']): r['img_per_s'] for r in results['latency'] if r['batch'] == 16}
    for r in results['accuracy']:
        x = speed[(r['backend'], r['precision'])]
        tensorrt = r['backend'] == 'TensorRT'
        ax.scatter(x, r['map50'], s=55, marker='o' if tensorrt else 's', lw=1.5, zorder=3,
                   facecolor=COLOR[r['precision']] if tensorrt else 'white', edgecolor=COLOR[r['precision']])
        dx, dy, align = LABEL_PLACE.get((r['backend'], r['precision']), (0, -26, 'center'))
        ax.annotate(f"{r['backend']} {r['precision']}\n{r['map50']:.2f}", (x, r['map50']), xytext=(dx, dy),
                    textcoords='offset points', ha=align, fontsize=8, color='#444444')
    ax.set_xlabel('throughput at batch 16 (images / s, model only)')
    ax.set_ylabel('split_val mAP@0.5')
    ax.set_ylim(82.5, 84.5)
    ax.grid(axis='x', color='#e6e6e6')
    ax.margins(x=0.2)


for name, draw in [('latency', lambda ax: plot_by_batch(ax, 'mean_ms', 'latency per batch (ms)')),
                   ('throughput', lambda ax: plot_by_batch(ax, 'img_per_s', 'throughput (images / s)')),
                   ('speed_vs_accuracy', plot_speed_vs_accuracy)]:
    fig, ax = plt.subplots(figsize=(5, 3.4))
    draw(ax)
    if name != 'speed_vs_accuracy':
        ax.legend(fontsize=8, loc='upper left')
    fig.savefig(FOLDER / f'{name}.png')

fig, axes = plt.subplots(1, 3, figsize=(14, 3.6), gridspec_kw={'wspace': 0.32})
plot_by_batch(axes[0], 'mean_ms', 'latency per batch (ms)')
axes[0].legend(fontsize=7.5, loc='upper left')
plot_by_batch(axes[1], 'img_per_s', 'throughput (images / s)')
plot_speed_vs_accuracy(axes[2])
for ax, title in zip(axes, ['Latency', 'Throughput', 'Speed vs accuracy']):
    ax.set_title(title, loc='left', fontsize=10.5)
fig.suptitle('YOLO26-L 1920 on one H200, 1920×1920 input', x=0.125, ha='left', fontsize=11.5, y=1.03)
fig.savefig(FOLDER / 'summary.png')

# markdown table
header = '| Backend | Precision | ' + ' | '.join(f'batch {b} (ms)' for b in BATCHES) + ' | img/s @16 | mAP@0.5 | end-to-end img/s |'
lines = [header, '|' + '---|' * (len(BATCHES) + 5)]
accuracy = {(r['backend'], r['precision']): r for r in results['accuracy']}
for backend in ['TensorRT', 'PyTorch']:
    for precision in COLOR:
        batches, ms = curve(backend, precision, 'mean_ms')
        if not batches:
            continue
        _, speed = curve(backend, precision, 'img_per_s')
        a = accuracy[(backend, precision)]
        lines.append(f'| {backend} | {precision} | ' + ' | '.join(f'{v:.1f}' for v in ms)
                     + f' | {speed[-1]:.0f} | {a["map50"]:.2f} | {a["end_to_end_img_per_s"]:.0f} |')
(FOLDER / 'table.md').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))

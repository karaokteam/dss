"""An image set is "test", "split_val" or a folder of .jpg images."""
from pathlib import Path

import pandas as pd

from . import metric, paths


def load(name):
    """Returns image ids (in output order) and {id: file}."""
    if name == 'test':
        folder = paths.TEST_IMAGES
        ids = pd.read_csv(paths.SAMPLE_SUBMISSION).image_id.tolist()
    elif name == 'split_val':
        benchmark = metric.load_benchmark(name)
        folder = Path(benchmark['image_dir'])
        ids = sorted(benchmark['images'])
    else:
        folder = Path(name)
        ids = sorted(p.stem for p in folder.glob('*.jpg'))
    files = {p.stem: p for p in folder.iterdir()}
    return ids, files


def output_dir(name):
    return paths.PREDICTIONS / Path(name).name

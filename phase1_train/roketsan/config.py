import yaml

from . import paths


def load():
    return yaml.safe_load(paths.CONFIG.read_text())


def weight_file(cfg, model, variant):
    """variant 'full' = trained on all data (test set), 'split' = trained on 70% (split_val)."""
    return paths.WEIGHTS / cfg['models'][model][variant]


def families(cfg):
    """Model names in the order they first appear in the pass list."""
    names = []
    for p in cfg['passes']:
        if p['model'] not in names:
            names.append(p['model'])
    return names

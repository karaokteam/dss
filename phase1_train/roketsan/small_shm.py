"""Only for machines with a tiny /dev/shm (ours had 64 MB): dataloader workers pass big tensors through /tmp files."""
import os
import shutil
import uuid
from multiprocessing.reduction import ForkingPickler

import numpy as np
import torch

FOLDER = '/tmp/torch_transfer'


def _load(path, dtype, shape):
    array = np.fromfile(path, dtype=dtype).reshape(shape)
    os.unlink(path)
    return torch.from_numpy(array)


def _dump(tensor):
    array = tensor.numpy()
    if array.nbytes < 1 << 20:
        return torch.from_numpy, (array,)
    path = f'{FOLDER}/{uuid.uuid4().hex}'
    array.tofile(path)
    return _load, (path, array.dtype.str, array.shape)


def install():
    shutil.rmtree(FOLDER, ignore_errors=True)
    os.makedirs(FOLDER)
    ForkingPickler.register(torch.Tensor, _dump)

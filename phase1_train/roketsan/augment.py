"""Extra photometric augmentation for the "augmented" YOLO model: the test images come from other places and cameras.

It replaces Ultralytics' Albumentations step (a no-op when albumentations is not installed). Boxes are unchanged.
"""
import random

import cv2
import numpy as np


def robust_photometric(self, labels):
    im = labels['img']

    if random.random() < 0.15:   # blur
        im = cv2.GaussianBlur(im, (0, 0), random.uniform(0.5, 1.5))

    if random.random() < 0.10:   # haze
        a = random.uniform(0.05, 0.25)
        im = (im * (1 - a) + random.uniform(180, 255) * a).clip(0, 255).astype(np.uint8)

    if random.random() < 0.20:   # exposure
        gamma = random.uniform(0.7, 1.4)
        lut = ((np.arange(256) / 255) ** gamma * 255).clip(0, 255).astype(np.uint8)
        im = cv2.LUT(im, lut)

    if random.random() < 0.20:   # white balance
        im = (im * np.random.uniform(0.9, 1.1, 3)).clip(0, 255).astype(np.uint8)

    if random.random() < 0.05:   # channel shuffle
        im = im[..., np.random.permutation(3)]

    if random.random() < 0.10:   # JPEG artefacts
        _, buf = cv2.imencode('.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, random.randint(40, 90)])
        im = cv2.imdecode(buf, cv2.IMREAD_COLOR)

    labels['img'] = np.ascontiguousarray(im)
    return labels


def install():
    from ultralytics.data import augment
    augment.Albumentations.__call__ = robust_photometric

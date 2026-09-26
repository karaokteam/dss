"""Vehicle crops for the two classifiers (each exactly as it was trained)."""
import numpy as np
from PIL import Image, ImageOps

GREY = 114


def square_crop(image, x, y, w, h, size=224):
    """DINOv2 car/van classifier: a square twice the box's long side, centred on it, grey outside the image."""
    side = max(int(round(2 * max(w, h))), 2)
    left = int(round(x + w / 2 - side / 2))
    top = int(round(y + h / 2 - side / 2))

    crop = np.full((side, side, 3), GREY, np.uint8)
    H, W = image.shape[:2]
    x1, y1 = max(0, left), max(0, top)
    x2, y2 = min(W, left + side), min(H, top + side)
    if x2 > x1 and y2 > y1:
        crop[y1 - top:y2 - top, x1 - left:x2 - left] = image[y1:y2, x1:x2]
    return np.asarray(Image.fromarray(crop).resize((size, size), Image.BILINEAR))


def margin_crop(image, x, y, w, h, size=128):
    """ConvNeXt classifier: the box plus a 12% margin, padded to a square with grey."""
    W, H = image.size
    mx, my = w * 0.12, h * 0.12
    left, top = max(0, int(round(x - mx))), max(0, int(round(y - my)))
    right, bottom = min(W, int(round(x + w + mx))), min(H, int(round(y + h + my)))

    crop = image.crop((left, top, right, bottom))
    side = max(crop.size)
    crop = ImageOps.pad(crop, (side, side), color=(GREY, GREY, GREY))
    return np.asarray(crop.resize((size, size), Image.BILINEAR))

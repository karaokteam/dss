import json

import pytest

from agent import config
from agent.schemas import ImageMeta, ZonesFile


@pytest.fixture
def meta_860() -> ImageMeta:
    raw = json.loads((config.SAMPLES_DIR / "image_meta_sample.json").read_text())
    return ImageMeta(image_id="img_000860", **raw["img_000860"])


@pytest.fixture
def zones_sample() -> ZonesFile:
    return ZonesFile(**json.loads((config.SAMPLES_DIR / "zones_sample.json").read_text()))


requires_raw_data = pytest.mark.skipif(not config.IMAGE_META_PATH.exists(), reason="data/raw yok")

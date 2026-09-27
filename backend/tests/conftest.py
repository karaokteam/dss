import pytest

from backend.config import settings as _settings

# Testlerde tekrar tekrar kullanılan, gerçek veriden bilinen örnek
SAMPLE_IMAGE = "img_000267"
SAMPLE_TRUCK_DET = "img_000267_003"
SAMPLE_TRUCK_TRACK = "T0045"


@pytest.fixture(scope="session")
def settings():
    return _settings


@pytest.fixture(scope="session", autouse=True)
def _require_data(settings):
    missing = [p for p in (settings.paths.image_meta, settings.paths.tracks,
                           settings.paths.reports, settings.paths.zones,
                           settings.paths.detections) if not p.exists()]
    if missing:
        pytest.exit(f"Veri dosyaları eksik: {missing}", returncode=2)

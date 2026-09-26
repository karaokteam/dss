"""Dosya yolları. Step 0 (hazır)"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / os.getenv(
    "DSS_DATA_DIR", "data/raw"
)  # göreli yol repo köküne göre (ör. DSS_DATA_DIR=/baska/yol)
SAMPLES_DIR = ROOT / "data" / "samples"
IMAGES_DIR = DATA_DIR / "images"
IMAGE_META_PATH = DATA_DIR / "image_meta.json"
ZONES_PATH = DATA_DIR / "zones.json"
TRACKS_PATH = DATA_DIR / "tracks.csv"
REPORTS_PATH = DATA_DIR / "field_reports.json"

MODELS_DIR = ROOT / "models"
MODEL_PATH = ROOT / os.getenv("DSS_MODEL_PATH", "models/best.pt")
CACHE_DIR = ROOT / "cache"
DETECTION_CACHE_DIR = CACHE_DIR / "detections"
LLM_CACHE_DIR = CACHE_DIR / "llm"

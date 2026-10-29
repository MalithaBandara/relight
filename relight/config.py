"""Paths and settings, read once from the environment (.env supported)."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache" / "model"
SCENARIO_DIR = ROOT / "scenarios"
MEDIA_DIR = ROOT / "media"
WEB_DIR = ROOT / "web"
DB_PATH = DATA_DIR / "galle.db"

MODEL_API_KEY = os.getenv("MODEL_API_KEY", "").strip()
META_API_BASE = os.getenv("META_API_BASE", "https://api.meta.ai/v1").rstrip("/")
SPARK_MODEL = os.getenv("SPARK_MODEL", "muse-spark-1.3")
TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "muse-voice-transcribe-1.0")
SAM_MODEL = os.getenv("SAM_MODEL", "sam-3.1")
GLIMMER_BASE = os.getenv("GLIMMER_BASE", "http://localhost:8001/v1").rstrip("/")
GLIMMER_MODEL = os.getenv("GLIMMER_MODEL", "muse-glimmer")

# "live" calls the Meta Model API; "mock" replays cached responses and falls back to
# the scenario's labelled ground truth. Defaults to live when a key is present.
MODEL_MODE = os.getenv("MODEL_MODE", "live" if MODEL_API_KEY else "mock")

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

DEFAULTS = {
    "names": [],
    "fuzzy_threshold": 0.84,
    "whisper_model": "base.en",
    "language": "en",
    "chunk_seconds": 5,
    "silence_rms": 0.004,
    "queue_max_chunks": 6,
    "context_seconds": 45,
    "post_roll_seconds": 8,
    "cooldown_seconds": 30,
    "ollama_enabled": True,
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "qwen2.5:3b",
    "ollama_timeout_seconds": 90,
    "save_events": True,
    "retention_hours": 24,
    "speaker_name": "",
    "auto_stop_silence_minutes": 10,
    "stop_when_teams_closed": True,
    "show_live_transcript_default": False,
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    return cfg


def save_config(cfg: dict, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

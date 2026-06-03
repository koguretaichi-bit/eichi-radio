"""設定とパスの一元管理。"""
from __future__ import annotations
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
EPISODES_DIR = DOCS_DIR / "episodes"
STATE_PATH = DATA_DIR / "state.json"
CLASSICS_PATH = DATA_DIR / "classics.json"
CONFIG_PATH = ROOT / "config.yaml"


def load_config() -> dict:
    load_dotenv(ROOT / ".env")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("_env", {})
    cfg["_env"]["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg["_env"]["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
    cfg["_env"]["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "")
    return cfg


def ensure_dirs() -> None:
    for d in (DATA_DIR, DOCS_DIR, EPISODES_DIR):
        d.mkdir(parents=True, exist_ok=True)

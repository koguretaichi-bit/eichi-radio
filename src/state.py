"""エピソード履歴(state.json)の読み書き。"""
from __future__ import annotations
import json
from .config import STATE_PATH


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"episodes": []}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def recent_classic_titles(state: dict, n: int = 7) -> list[str]:
    return [e.get("classic_title", "") for e in state["episodes"][-n:]]

"""古典をランダムに選ぶ。直近で使ったものは避ける。"""
from __future__ import annotations
import json
import random
from .config import CLASSICS_PATH


def pick_classic(recent_titles: list[str] | None = None) -> dict:
    with open(CLASSICS_PATH, "r", encoding="utf-8") as f:
        classics = json.load(f)

    recent = set(recent_titles or [])
    pool = [c for c in classics if c["title"] not in recent] or classics
    return random.choice(pool)

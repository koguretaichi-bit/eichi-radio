"""docs/ を git commit & push して GitHub Pages に反映する（任意）。"""
from __future__ import annotations
import subprocess
from .config import ROOT


def git_push(branch: str, message: str) -> None:
    def run(*args: str) -> str:
        return subprocess.run(
            args, cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout

    run("git", "add", "docs", "data/state.json")
    # 変更がなければ commit は失敗するので握りつぶす
    try:
        run("git", "commit", "-m", message)
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in (e.stdout + e.stderr):
            print("[publish] 変更なし。pushをスキップします。")
            return
        raise
    run("git", "push", "origin", branch)
    print("[publish] GitHub に push しました。")

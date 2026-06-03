"""叡智ラジオ Dead Reckoning — 1日分のエピソードを生成するメイン処理。

使い方:
  python -m src.main                # 通常実行（音声まで生成）
  python -m src.main --dry-run      # 台本だけ生成して表示（TTS課金なし）
  python -m src.main --rebuild-feed # 既存エピソードから feed.xml だけ作り直す
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone

from .config import load_config, ensure_dirs, EPISODES_DIR
from . import news as news_mod
from . import classics as classics_mod
from . import script_gen
from . import tts as tts_mod
from . import feed as feed_mod
from . import state as state_mod
from . import publish


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="台本のみ生成（TTSしない）")
    ap.add_argument("--rebuild-feed", action="store_true", help="feed.xmlの再生成のみ")
    ap.add_argument("--topic", type=str, default="", help="お題を指定して作る（ニュースの代わり）")
    ap.add_argument("--title", type=str, default="", help="エピソードのタイトルを固定する")
    args = ap.parse_args()

    cfg = load_config()
    ensure_dirs()
    st = state_mod.load_state()

    if args.rebuild_feed:
        feed_mod.build_feed(cfg, st)
        print("feed.xml と index.html を再生成しました。")
        return 0

    _check_keys(cfg, need_audio=not args.dry_run)

    if args.topic:
        # お題モード: ニュースの代わりにテーマを使い、古典はAIが選ぶ
        news_items = []
        print(f"[1/5] お題: {args.topic}")
        print("[2/5] 古典はAIが選択します")
        print(f"[3/5] 台本を生成中（{cfg['script']['provider']}）...")
        script = script_gen.generate_topic_script(cfg, args.topic)
        classic = {"title": script["classic_title"], "author": script["classic_author"]}
        print(f"   📚 選ばれた古典: {classic['title']}（{classic['author']}）")
    else:
        # 1. ニュース
        print("[1/5] ニュースを取得中...")
        news_items = news_mod.pick_news(cfg["news"]["feeds"], cfg["news"]["pick_count"])
        for n in news_items:
            print(f"   📰 [{n['source']}] {n['title']}")

        # 2. 古典
        print("[2/5] 古典を選択中...")
        classic = classics_mod.pick_classic(state_mod.recent_classic_titles(st))
        print(f"   📚 {classic['title']}（{classic['author']}）")

        # 3. 台本
        print(f"[3/5] 台本を生成中（{cfg['script']['provider']}）...")
        script = script_gen.generate_script(cfg, news_items, classic)

    if args.title:
        script["title"] = args.title
    print(f"   🎬 タイトル: {script['title']}（{len(script['turns'])}ターン）")

    if args.dry_run:
        print("\n===== 台本（dry-run）=====\n")
        for t in script["turns"]:
            who = cfg["script"]["sage_name"] if t["speaker"] == "sage" else cfg["script"]["learner_name"]
            print(f"【{who}】{t['text']}\n")
        return 0

    # 4. 音声
    now = datetime.now(timezone.utc)
    ep_id = now.strftime("ep-%Y%m%d-%H%M")
    filename = f"{ep_id}.mp3"
    out_path = EPISODES_DIR / filename

    # 書き起こし（台本）をUTF-8で保存
    transcript_path = EPISODES_DIR / f"{ep_id}.txt"
    _save_transcript(transcript_path, cfg, script, classic, news_items)
    print(f"   📝 書き起こし: {transcript_path}")

    print(f"[4/5] 音声を生成中（{cfg['tts']['provider']} TTS）...")
    size, duration = tts_mod.synthesize(cfg, script["turns"], out_path)
    print(f"   🔊 {filename}  {size/1_000_000:.1f}MB  {duration//60}分{duration%60}秒")

    # 5. フィード更新
    print("[5/5] RSS / index.html を更新中...")
    st["episodes"].append(
        {
            "id": ep_id,
            "title": script["title"],
            "filename": filename,
            "pubdate": now.isoformat(),
            "duration": duration,
            "bytes": size,
            "show_notes": script.get("show_notes", ""),
            "classic_title": classic["title"],
            "classic_author": classic["author"],
            "news": [{"title": n["title"], "source": n["source"], "link": n["link"]} for n in news_items],
        }
    )
    state_mod.save_state(st)
    feed_mod.build_feed(cfg, st)

    if cfg["publish"].get("auto_git_push"):
        # 公開(push)が失敗しても、番組生成自体は成功とする
        try:
            publish.git_push(cfg["publish"]["git_branch"], f"Add episode: {script['title']}")
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠ 自動push失敗（番組は生成済み）: {e}")

    base = cfg["podcast"]["base_url"].rstrip("/")
    print(f"\n✅ 完成: {script['title']}")
    print(f"   RSS: {base}/feed.xml")
    return 0


def _save_transcript(path, cfg, script, classic, news_items) -> None:
    sage = cfg["script"]["sage_name"]
    learner = cfg["script"]["learner_name"]
    lines = [
        f"# {script['title']}",
        "",
        f"古典: {classic['title']}（{classic['author']}）",
    ]
    if news_items:
        lines.append("ニュース: " + " / ".join(n["title"] for n in news_items))
    lines += [
        "",
        script.get("show_notes", ""),
        "",
        "----",
        "",
    ]
    for t in script["turns"]:
        who = sage if t["speaker"] == "sage" else learner
        lines.append(f"【{who}】{t['text']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _check_keys(cfg: dict, need_audio: bool) -> None:
    missing = []
    sp = cfg["script"].get("provider", "gemini")
    if sp == "gemini" and not cfg["_env"]["GOOGLE_API_KEY"]:
        missing.append("GOOGLE_API_KEY（無料・https://aistudio.google.com/apikey）")
    elif sp == "claude" and not cfg["_env"]["ANTHROPIC_API_KEY"]:
        missing.append("ANTHROPIC_API_KEY")

    if need_audio and cfg["tts"].get("provider") == "openai" and not cfg["_env"]["OPENAI_API_KEY"]:
        missing.append("OPENAI_API_KEY")
    # tts.provider == "edge" はキー不要

    if missing:
        print(f"❌ .env に次のキーがありません: {', '.join(missing)}")
        print("   .env.example を .env にコピーして設定してください。")
        sys.exit(1)


if __name__ == "__main__":
    raise SystemExit(main())

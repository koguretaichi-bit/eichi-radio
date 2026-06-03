"""RSSフィードから今日のニュースをランダムに拾う（APIキー不要）。"""
from __future__ import annotations
import random
import feedparser


def pick_news(feeds: list[str], count: int = 1) -> list[dict]:
    """設定されたフィードを巡回し、最近の記事からランダムに count 件選ぶ。"""
    entries: list[dict] = []
    feeds = list(feeds)
    random.shuffle(feeds)

    for url in feeds:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        source = parsed.feed.get("title", url)
        # 各フィードの新着上位だけを候補に（鮮度確保）
        for e in parsed.entries[:15]:
            title = (e.get("title") or "").strip()
            if not title:
                continue
            summary = (e.get("summary") or e.get("description") or "").strip()
            # HTMLタグの簡易除去
            summary = _strip_html(summary)[:600]
            entries.append(
                {
                    "title": title,
                    "summary": summary,
                    "link": e.get("link", ""),
                    "source": source,
                }
            )

    if not entries:
        raise RuntimeError(
            "ニュースを1件も取得できませんでした。config.yaml の news.feeds を確認してください。"
        )

    random.shuffle(entries)
    return entries[:count]


def _strip_html(text: str) -> str:
    out = []
    depth = 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out).strip()

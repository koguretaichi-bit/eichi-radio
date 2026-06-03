"""state.json から Podcast RSS (feed.xml) と一覧ページ(index.html)を生成する。"""
from __future__ import annotations
from datetime import datetime, timezone
from email.utils import format_datetime
from feedgen.feed import FeedGenerator
from .config import DOCS_DIR


def _fmt_duration(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def build_feed(cfg: dict, state: dict) -> None:
    p = cfg["podcast"]
    base = p["base_url"].rstrip("/")

    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(p["title"])
    fg.link(href=f"{base}/feed.xml", rel="self")
    fg.link(href=base, rel="alternate")
    fg.description(p["description"].strip())
    fg.language(p.get("language", "ja"))
    fg.author({"name": p["author"], "email": p["email"]})
    fg.logo(f"{base}/{p['cover_image']}")
    fg.image(url=f"{base}/{p['cover_image']}", title=p["title"], link=base)

    fg.podcast.itunes_author(p["author"])
    fg.podcast.itunes_summary(p["description"].strip())
    fg.podcast.itunes_subtitle(p.get("subtitle", ""))
    fg.podcast.itunes_owner(name=p["author"], email=p["email"])
    fg.podcast.itunes_image(f"{base}/{p['cover_image']}")
    fg.podcast.itunes_category(p.get("category", "Society & Culture"))
    fg.podcast.itunes_explicit("yes" if p.get("explicit") else "no")

    # 新しい順に並べる（RSSは任意順だが見やすさ優先）
    for ep in state["episodes"]:
        fe = fg.add_entry()
        url = f"{base}/episodes/{ep['filename']}"
        fe.id(url)
        fe.title(ep["title"])
        fe.description(ep.get("show_notes", ""))
        fe.enclosure(url, str(ep["bytes"]), "audio/mpeg")
        fe.published(_parse_dt(ep["pubdate"]))
        fe.podcast.itunes_duration(_fmt_duration(ep["duration"]))
        fe.podcast.itunes_explicit("no")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(DOCS_DIR / "feed.xml"), pretty=True)
    _build_index(cfg, state)


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _build_index(cfg: dict, state: dict) -> None:
    p = cfg["podcast"]
    base = p["base_url"].rstrip("/")
    items = ""
    for ep in reversed(state["episodes"]):
        # 相対パス: ローカルで開いても、GitHub Pagesでも同じHTMLで再生できる
        url = f"episodes/{ep['filename']}"
        txt = f"episodes/{ep['id']}.txt"
        date = _parse_dt(ep["pubdate"]).strftime("%Y-%m-%d")
        items += f"""
      <article class="ep">
        <h2>{_esc(ep['title'])}</h2>
        <p class="meta">{date} ・ {_fmt_duration(ep['duration'])} ・ 古典: {_esc(ep.get('classic_title',''))} ・ <a href="{txt}">書き起こし</a></p>
        <p class="notes">{_esc(ep.get('show_notes',''))}</p>
        <audio controls preload="none" src="{url}"></audio>
      </article>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(p['title'])}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 760px; margin: 0 auto; padding: 2rem 1rem; line-height: 1.7; color:#1a1a1a; background:#fafafa; }}
  header {{ border-bottom: 2px solid #222; padding-bottom: 1rem; margin-bottom: 2rem; }}
  h1 {{ margin: 0; font-size: 1.8rem; }}
  .sub {{ color:#555; margin:.3rem 0 0; }}
  .feed-link {{ display:inline-block; margin-top:.8rem; font-size:.9rem; }}
  .ep {{ background:#fff; border:1px solid #e2e2e2; border-radius:12px; padding:1.2rem 1.4rem; margin-bottom:1.2rem; }}
  .ep h2 {{ margin:0 0 .3rem; font-size:1.2rem; }}
  .meta {{ color:#888; font-size:.85rem; margin:0 0 .6rem; }}
  .notes {{ margin:0 0 .8rem; }}
  audio {{ width:100%; }}
</style>
</head>
<body>
  <header>
    <h1>{_esc(p['title'])}</h1>
    <p class="sub">{_esc(p.get('subtitle',''))}</p>
    <a class="feed-link" href="feed.xml">📡 RSSフィード (Spotify登録用)</a>
  </header>
  <main>{items if items else '<p>まだエピソードがありません。</p>'}
  </main>
</body>
</html>"""
    with open(DOCS_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

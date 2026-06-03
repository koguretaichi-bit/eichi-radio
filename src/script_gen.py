"""対話形式の台本を生成する。

provider:
  - "gemini": Google Gemini（無料枠・クレカ不要）
  - "claude": Anthropic Claude（要クレジット）
"""
from __future__ import annotations
import json
import re
import time

SYSTEM = """あなたは教養ラジオ番組『叡智ラジオ Dead Reckoning』の構成作家兼演出家です。
番組コンセプト: GPSのなかった時代の航海術「デッド・レコニング（推測航法）」になぞらえ、
古典という過去の確かな知から、いま起きているニュースという現在地を読み解きます。

出演は2人だけ。AIが演じます。
- 賢者: 該当する古典に深く通じ、落ち着いて本質を語る。決めつけず、しかし鋭い。
- 聞き手: 知的好奇心の強い学び手。素朴で的確な問いでリスナーの疑問を代弁し、話を深掘りする。

台本の質の基準:
- 単なるニュース要約ではなく「古典のレンズで現在を読み解く」こと。両者を必ず往復させる。
- 古典の具体的な概念・章句・エピソードを引きながら、現代の出来事に接続する。
- 安易な結論を出さず、複数の見方や緊張関係を提示する。リスナーに考える余地を残す。
- 自然な話し言葉。相づち、言い換え、たとえ話を使う。ただし冗長にしない。
- 冒頭に番組名と今日のテーマの導入、最後に短いまとめと次回への余韻を入れる。
- 音声で読み上げるので、○○・△△・(名前)のようなプレースホルダや記号は絶対に使わない。
  自己紹介で固有名を名乗る必要はなく、名乗るなら賢者・聞き手とだけ言う。
- URL、絵文字、箇条書き記号、見出し記号など、声に出すと不自然なものは本文に入れない。
"""

USER_TEMPLATE = """# 今日の素材

## ニュース
{news_block}

## 今日の古典
- 書名: {classic_title}（{classic_author}）
- レンズ: {classic_lens}

# 指示
上記のニュースを、この古典のレンズで読み解く対話台本を作ってください。
- 目安の長さ: 音声で約{minutes}分（日本語で読み上げる分量に調整）。
- 賢者と聞き手の自然な対話。話者は交互でなくてよい（同じ人が続けてもよい）。
- 固有名詞や数字はニュース素材の範囲で扱い、断定的なデマを作らない。不確かな点は「報じられている」等の留保をつける。

# 出力フォーマット（厳守）
次のJSONだけを出力してください。前後に説明文やコードフェンスを付けないこと。
{{
  "title": "エピソードのタイトル（例: AI規制とマキャヴェリ）",
  "show_notes": "2〜4文の番組説明。今日のニュースと古典の組み合わせを紹介する。",
  "turns": [
    {{"speaker": "learner", "text": "..."}},
    {{"speaker": "sage", "text": "..."}}
  ]
}}
speaker は "sage"（賢者）か "learner"（聞き手）のいずれか。"""


TOPIC_TEMPLATE = """# 今日のテーマ（お題指定）
{topic}

# 指示
このテーマを、最もふさわしい古典のレンズで掘り下げる対話台本を作ってください。
- まず、このテーマに最も響き合う古典を1〜2冊あなた自身が選ぶ（東洋・西洋どちらでもよい）。
- 選んだ古典の具体的な概念・章句・エピソードを引きながら、テーマを現代のビジネスや人間関係の文脈で読み解く。
- 目安の長さ: 音声で約{minutes}分（日本語で読み上げる分量に調整）。
- 賢者と聞き手の自然な対話。話者は交互でなくてよい。
- 安易な結論を出さず、複数の見方や緊張関係を提示する。

# 出力フォーマット（厳守）
次のJSONだけを出力してください。前後に説明文やコードフェンスを付けないこと。
{{
  "title": "エピソードのタイトル",
  "classic_title": "中心に据えた古典の書名",
  "classic_author": "その著者",
  "show_notes": "2〜4文の番組説明。テーマと用いた古典を紹介する。",
  "turns": [
    {{"speaker": "learner", "text": "..."}},
    {{"speaker": "sage", "text": "..."}}
  ]
}}
speaker は "sage"（賢者）か "learner"（聞き手）のいずれか。"""


def generate_topic_script(cfg: dict, topic: str) -> dict:
    sc = cfg["script"]
    provider = sc.get("provider", "gemini")
    minutes = sc["target_minutes"]
    user = TOPIC_TEMPLATE.format(topic=topic, minutes=minutes)

    if provider == "gemini":
        text = _gemini(cfg["_env"]["GOOGLE_API_KEY"], sc["model"], user)
    elif provider == "claude":
        text = _claude(cfg["_env"]["ANTHROPIC_API_KEY"], sc["model"], user, minutes)
    else:
        raise ValueError(f"未知の script.provider: {provider}")

    data = _extract_json(text)
    turns = [t for t in data.get("turns", []) if t.get("text", "").strip()]
    if not turns:
        raise RuntimeError("台本のturnsが空でした。モデル出力:\n" + text[:1000])
    data["turns"] = turns
    data.setdefault("title", topic)
    data.setdefault("classic_title", "（古典）")
    data.setdefault("classic_author", "")
    data.setdefault("show_notes", "")
    return data


def generate_script(cfg: dict, news_items: list[dict], classic: dict) -> dict:
    sc = cfg["script"]
    provider = sc.get("provider", "gemini")
    minutes = sc["target_minutes"]

    news_block = "\n\n".join(
        f"- [{n['source']}] {n['title']}\n  {n['summary']}" for n in news_items
    )
    user = USER_TEMPLATE.format(
        news_block=news_block,
        classic_title=classic["title"],
        classic_author=classic["author"],
        classic_lens=classic["lens"],
        minutes=minutes,
    )

    if provider == "gemini":
        text = _gemini(cfg["_env"]["GOOGLE_API_KEY"], sc["model"], user)
    elif provider == "claude":
        text = _claude(cfg["_env"]["ANTHROPIC_API_KEY"], sc["model"], user, minutes)
    else:
        raise ValueError(f"未知の script.provider: {provider}")

    data = _extract_json(text)
    turns = [t for t in data.get("turns", []) if t.get("text", "").strip()]
    if not turns:
        raise RuntimeError("台本のturnsが空でした。モデル出力:\n" + text[:1000])
    data["turns"] = turns
    data.setdefault("title", f"{classic['title']}で読む今日のニュース")
    data.setdefault("show_notes", "")
    return data


def _retry(fn, attempts: int = 5, label: str = "API"):
    """一時的なサーバ混雑（503/429/500）にリトライで耐える。"""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            transient = any(c in msg for c in ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded"))
            last = e
            if not transient or attempt == attempts:
                raise
            wait = min(2 ** attempt, 30)
            print(f"   ⚠ {label}再試行 {attempt}/{attempts}: {msg.splitlines()[0][:60]} → {wait}s待機")
            time.sleep(wait)
    raise last


def _gemini(api_key: str, model: str, user: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    def call():
        return client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )

    resp = _retry(call, label="Gemini")
    return resp.text or ""


def _claude(api_key: str, model: str, user: str, minutes: int) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    max_tokens = min(16000, 1200 + minutes * 700)

    def call():
        return client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
        )

    resp = _retry(call, label="Claude")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)

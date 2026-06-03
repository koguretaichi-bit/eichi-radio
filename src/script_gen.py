"""対話形式の台本を生成する。

provider:
  - "gemini": Google Gemini（無料枠・クレカ不要）
  - "claude": Anthropic Claude（要クレジット）
"""
from __future__ import annotations
import json
import re
import time

SYSTEM_TEMPLATE = """あなたは教養ラジオ番組『アイディアのアウフヘーベン』の構成作家兼演出家です。
番組コンセプト: 毎日のニュースを題材に、ビジネスパーソンの「信頼構築」という視点から、
古典の英知をもとに実践的なアドバイスを贈ります。ニュース（いま起きている事実）と古典（時代を超えた知恵）を
ぶつけ合わせ、対立や矛盾を切り捨てずに抱え込みながら、一段上の洞察へと止揚（アウフヘーベン）し、
聞き手が明日の仕事で「信頼を築く・保つ・取り戻す」ために使える視点へと変えていきます。

出演は2人。AIが演じます。
- {sage}: 賢者役。古典に深く通じ、信頼や人間関係の本質を落ち着いて説く。決めつけず、しかし鋭い。
- {learner}: 聞き手役。ビジネスの現場感覚を持つ学び手。素朴で的確な問いでリスナーを代弁し、話を実務に引き寄せる。

台本の質の基準:
- 単なるニュース要約ではなく「古典のレンズでニュースを読み解き、ビジネスの信頼構築に効く実践的アドバイスへ止揚する」こと。
- 古典の具体的な概念・章句・エピソードを引きながら、現代のビジネス（職場・取引・組織・顧客・チーム）の文脈に接続する。
- 聞き手が明日から試せる具体的な行動や問いを、少なくとも1つは含める。
- 対立する見方や緊張関係も示し、安易な結論は避けつつ、最後は「信頼」という観点での示唆に着地させる。
- 自然な話し言葉。相づち、言い換え、たとえ話を使う。冗長にしない。{sage}と{learner}は時折たがいを名前で呼び合う。
- 冒頭に番組名『アイディアのアウフヘーベン』と今日のテーマの導入、最後に短いまとめと次回への余韻を入れる。
- 音声で読み上げるので、○○・△△・(名前)のようなプレースホルダや記号は絶対に使わない。
- URL、絵文字、箇条書き記号、見出し記号など、声に出すと不自然なものは本文に入れない。
"""

USER_TEMPLATE = """# 今日の素材

## ニュース
{news_block}

## 今日の古典
- 書名: {classic_title}（{classic_author}）
- レンズ: {classic_lens}

# 指示
上記のニュースを題材に、ビジネスパーソンの「信頼構築」の視点から、この古典の英知をもとにアドバイスする対話台本を作ってください。
- 目安の長さ: 音声で約{minutes}分（日本語で読み上げる分量に調整）。
- {sage}と{learner}の自然な対話。話者は交互でなくてよい（同じ人が続けてもよい）。
- ニュースの事実関係は素材の範囲で扱い、断定的なデマを作らない。不確かな点は「報じられている」等の留保をつける。
- 聞き手が明日の仕事で信頼を築く・保つ・取り戻すために使える、具体的な視点や行動を必ず含める。

# 出力フォーマット（厳守）
次のJSONだけを出力してください。前後に説明文やコードフェンスを付けないこと。
{{
  "title": "エピソードのタイトル",
  "show_notes": "2〜4文の番組説明。今日のニュースと古典、そして信頼構築の切り口を紹介する。",
  "turns": [
    {{"speaker": "learner", "text": "..."}},
    {{"speaker": "sage", "text": "..."}}
  ]
}}
speaker は "sage"（{sage}）か "learner"（{learner}）のいずれか。"""


TOPIC_TEMPLATE = """# 今日のテーマ（お題指定）
{topic}

# 指示
このテーマを、ビジネスパーソンの「信頼構築」の視点から、最もふさわしい古典の英知をもとに掘り下げる対話台本を作ってください。
- まず、このテーマに最も響き合う古典を1〜2冊あなた自身が選ぶ（東洋・西洋どちらでもよい）。
- 選んだ古典の具体的な概念・章句・エピソードを引きながら、テーマを現代のビジネスや人間関係の文脈で読み解く。
- 目安の長さ: 音声で約{minutes}分（日本語で読み上げる分量に調整）。
- {sage}と{learner}の自然な対話。話者は交互でなくてよい。
- 聞き手が明日から使える具体的な視点や行動を必ず含める。

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
speaker は "sage"（{sage}）か "learner"（{learner}）のいずれか。"""


def _names(cfg: dict) -> tuple[str, str]:
    sc = cfg["script"]
    return sc.get("sage_name", "先生"), sc.get("learner_name", "ミシェル")


def _system(cfg: dict) -> str:
    sage, learner = _names(cfg)
    return SYSTEM_TEMPLATE.format(sage=sage, learner=learner)


def generate_topic_script(cfg: dict, topic: str) -> dict:
    sc = cfg["script"]
    provider = sc.get("provider", "gemini")
    minutes = sc["target_minutes"]
    sage, learner = _names(cfg)
    user = TOPIC_TEMPLATE.format(topic=topic, minutes=minutes, sage=sage, learner=learner)
    text = _call(cfg, provider, _system(cfg), user, minutes)

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
    sage, learner = _names(cfg)

    news_block = "\n\n".join(
        f"- [{n['source']}] {n['title']}\n  {n['summary']}" for n in news_items
    )
    user = USER_TEMPLATE.format(
        news_block=news_block,
        classic_title=classic["title"],
        classic_author=classic["author"],
        classic_lens=classic["lens"],
        minutes=minutes,
        sage=sage,
        learner=learner,
    )
    text = _call(cfg, provider, _system(cfg), user, minutes)

    data = _extract_json(text)
    turns = [t for t in data.get("turns", []) if t.get("text", "").strip()]
    if not turns:
        raise RuntimeError("台本のturnsが空でした。モデル出力:\n" + text[:1000])
    data["turns"] = turns
    data.setdefault("title", f"{classic['title']}で読む今日のニュース")
    data.setdefault("show_notes", "")
    return data


def _call(cfg: dict, provider: str, system: str, user: str, minutes: int) -> str:
    if provider == "gemini":
        return _gemini(cfg["_env"]["GOOGLE_API_KEY"], cfg["script"]["model"], system, user)
    if provider == "claude":
        return _claude(cfg["_env"]["ANTHROPIC_API_KEY"], cfg["script"]["model"], system, user, minutes)
    raise ValueError(f"未知の script.provider: {provider}")


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


def _gemini(api_key: str, model: str, system: str, user: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    def call():
        return client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )

    resp = _retry(call, label="Gemini")
    return resp.text or ""


def _claude(api_key: str, model: str, system: str, user: str, minutes: int) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    max_tokens = min(16000, 1200 + minutes * 700)

    def call():
        return client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
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

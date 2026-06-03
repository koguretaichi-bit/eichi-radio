"""台本を音声化し、1本のMP3に結合する（ffmpeg不要）。

provider:
  - "edge"  : Edge TTS（完全無料・APIキー不要）
  - "openai": OpenAI TTS（要クレジット）
"""
from __future__ import annotations
import asyncio
import re
from pathlib import Path
from mutagen.mp3 import MP3

MAX_CHARS = 3000  # 1リクエストあたりの文字上限の目安


def synthesize(cfg: dict, turns: list[dict], out_path: Path) -> tuple[int, int]:
    """台本を音声化して out_path に書き出す。(バイト数, 秒数) を返す。"""
    tts_cfg = cfg["tts"]
    provider = tts_cfg.get("provider", "edge")

    if provider == "edge":
        chunks = _edge_synth(tts_cfg, turns)
    elif provider == "xtts":
        chunks = _xtts_synth(tts_cfg, turns)
    elif provider == "openai":
        chunks = _openai_synth(cfg["_env"]["OPENAI_API_KEY"], tts_cfg, turns)
    else:
        raise ValueError(f"未知の tts.provider: {provider}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for c in chunks:
            f.write(c)

    size = out_path.stat().st_size
    try:
        duration = int(MP3(out_path).info.length)
    except Exception:
        duration = max(1, size // 32000)
    return size, duration


# ---------- Edge TTS（無料） ----------
def _edge_synth(tts_cfg: dict, turns: list[dict]) -> list[bytes]:
    sage_voice = tts_cfg["edge_sage_voice"]
    learner_voice = tts_cfg["edge_learner_voice"]
    # speed 1.0 -> "+0%", 1.1 -> "+10%", 0.9 -> "-10%"
    rate = f"{round((tts_cfg.get('speed', 1.0) - 1.0) * 100):+d}%"

    jobs: list[tuple[str, str]] = []
    for turn in turns:
        voice = sage_voice if turn.get("speaker") == "sage" else learner_voice
        for piece in _split_text(turn["text"]):
            jobs.append((voice, piece))

    return asyncio.run(_edge_run(jobs, rate))


async def _edge_run(jobs: list[tuple[str, str]], rate: str) -> list[bytes]:
    import asyncio
    import edge_tts

    out: list[bytes] = []
    for i, (voice, text) in enumerate(jobs):
        out.append(await _edge_one(edge_tts, voice, text, rate, idx=i, total=len(jobs)))
    return out


async def _edge_one(edge_tts, voice, text, rate, idx, total, attempts=5):
    """1発話を合成。Edge TTSの一時的な503等にリトライで耐える。"""
    import asyncio

    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate)
            buf = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf += chunk["data"]
            if not buf:
                raise RuntimeError("空の音声が返りました")
            return buf
        except Exception as e:  # noqa: BLE001 - ネットワーク系の一時障害を広く捕捉
            last_err = e
            wait = min(2 ** attempt, 20)
            print(f"   ⚠ TTS再試行 {attempt}/{attempts}（{idx+1}/{total}）: {type(e).__name__} → {wait}s待機")
            await asyncio.sleep(wait)
    raise RuntimeError(f"TTS合成に失敗（{attempts}回試行）: {last_err}")


# ---------- XTTS-v2（無料・声クローン、ローカル実行） ----------
def _xtts_synth(tts_cfg: dict, turns: list[dict]) -> list[bytes]:
    import os
    from pathlib import Path

    # 8GB RAM・CPU環境での安定化（スレッド過多によるクラッシュを防ぐ）
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    import numpy as np
    import lameenc
    import torch
    torch.set_num_threads(int(tts_cfg.get("xtts_threads", 2)))
    from TTS.api import TTS

    import asyncio
    import edge_tts

    root = Path(__file__).resolve().parent.parent
    sage_wav = _ensure_wav(root / tts_cfg["xtts_sage_wav"])
    # 聞き手の声: "edge"(女性ニューラル/高速) か "clone"(別サンプルをクローン)
    learner_mode = tts_cfg.get("xtts_learner_mode", "edge")
    learner_wav = None
    if learner_mode == "clone":
        learner_wav = _ensure_wav(root / tts_cfg["xtts_learner_wav"])

    # XTTSの生成パラメータ（日本語の安定化）。文分割は自前で行う(spacy不要)。
    params = dict(
        temperature=float(tts_cfg.get("xtts_temperature", 0.7)),
        repetition_penalty=float(tts_cfg.get("xtts_repetition_penalty", 5.0)),
        length_penalty=float(tts_cfg.get("xtts_length_penalty", 1.0)),
        top_k=int(tts_cfg.get("xtts_top_k", 50)),
        top_p=float(tts_cfg.get("xtts_top_p", 0.85)),
        enable_text_splitting=False,
    )
    edge_voice = tts_cfg.get("edge_learner_voice", "ja-JP-NanamiNeural")
    rate = f"{round((tts_cfg.get('speed', 1.0) - 1.0) * 100):+d}%"

    print("   ⏳ XTTSモデルを読み込み中（初回はダウンロードあり）...")
    os.environ.setdefault("COQUI_TOS_AGREED", "1")  # 非対話環境でライセンス同意
    model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    sr = model.synthesizer.output_sample_rate  # 通常 24000

    out: list[bytes] = []
    total = len(turns)
    for i, turn in enumerate(turns):
        is_sage = turn.get("speaker") == "sage"
        if is_sage or learner_mode == "clone":
            wav = sage_wav if is_sage else learner_wav
            pcm_chunks = []
            for piece in _split_ja(turn["text"], limit=70):
                audio = model.tts(text=piece, speaker_wav=wav, language="ja", **params)
                pcm_chunks.append(np.asarray(audio, dtype=np.float32))
            sig = np.concatenate(pcm_chunks)
            out.append(_pcm_to_mp3(sig, sr, lameenc))
            print(f"   🎙 {i+1}/{total} 賢者(クローン) 合成完了")
        else:
            # 聞き手は Edge TTS（女性・高速・クリーン）
            buf = b""
            for piece in _split_text(turn["text"]):
                buf += asyncio.run(_edge_one(edge_tts, edge_voice, piece, rate, idx=i, total=total))
            out.append(buf)
            print(f"   🗣 {i+1}/{total} 聞き手(Edge) 合成完了")
    return out


def _split_ja(text: str, limit: int = 70) -> list[str]:
    """日本語テキストを、XTTSの文字数上限(約71)以下の塊に分割する。
    句点で文に分け、長い文は読点でさらに分け、それでも長ければ強制分割。"""
    import re

    text = text.strip()
    sents = [s for s in re.split(r"(?<=[。！？!?\n])", text) if s.strip()]
    pieces: list[str] = []
    for s in sents:
        s = s.strip()
        if len(s) <= limit:
            pieces.append(s)
            continue
        cur = ""
        for t in re.split(r"(?<=[、,，])", s):
            if len(cur) + len(t) <= limit:
                cur += t
            else:
                if cur:
                    pieces.append(cur)
                if len(t) <= limit:
                    cur = t
                else:
                    for j in range(0, len(t), limit):
                        pieces.append(t[j : j + limit])
                    cur = ""
        if cur:
            pieces.append(cur)
    return pieces or [text[:limit]]


def _ensure_wav(path) -> str:
    """声サンプルを XTTS が読めるwav(24kHzモノラル)に整える。m4a/mp3も自動変換。"""
    import os
    import subprocess
    from pathlib import Path

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"声サンプルが見つかりません: {path}")
    if path.suffix.lower() == ".wav":
        return str(path.resolve())

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out = path.with_suffix(".converted.wav")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(path), "-ar", "24000", "-ac", "1", str(out)],
        check=True, capture_output=True,
    )
    return str(out.resolve())


def _pcm_to_mp3(signal, sample_rate: int, lameenc) -> bytes:
    import numpy as np

    pcm16 = np.clip(signal, -1.0, 1.0)
    pcm16 = (pcm16 * 32767).astype("<i2").tobytes()
    enc = lameenc.Encoder()
    enc.set_bit_rate(128)
    enc.set_in_sample_rate(sample_rate)
    enc.set_channels(1)
    enc.set_quality(2)
    data = enc.encode(pcm16)
    data += enc.flush()
    return data


# ---------- OpenAI TTS（有料） ----------
def _openai_synth(api_key: str, tts_cfg: dict, turns: list[dict]) -> list[bytes]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model = tts_cfg["openai_model"]
    sage_voice = tts_cfg["openai_sage_voice"]
    learner_voice = tts_cfg["openai_learner_voice"]
    speed = tts_cfg.get("speed", 1.0)

    out: list[bytes] = []
    for turn in turns:
        voice = sage_voice if turn.get("speaker") == "sage" else learner_voice
        for piece in _split_text(turn["text"]):
            resp = client.audio.speech.create(
                model=model, voice=voice, input=piece,
                speed=speed, response_format="mp3",
            )
            out.append(resp.content)
    return out


def _split_text(text: str) -> list[str]:
    """長い発話を句点・改行でMAX_CHARS以下に分割する。"""
    text = text.strip()
    if len(text) <= MAX_CHARS:
        return [text]
    sentences = re.split(r"(?<=[。！？!?\n])", text)
    pieces, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) > MAX_CHARS and cur:
            pieces.append(cur)
            cur = s
        else:
            cur += s
    if cur.strip():
        pieces.append(cur)
    return pieces or [text[:MAX_CHARS]]

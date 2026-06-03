# 叡智ラジオ Dead Reckoning 🧭📻

> GPSのなかった時代、航海士は過去の位置から現在地を割り出した——デッド・レコニング。
> **古典の知恵を羅針盤に、今日のニュースを読み解く**完全AI自動生成ポッドキャスト。

毎朝7時に、ニュースをランダムに拾い→古典をランダムに選び→**賢者役と聞き手役の対話台本**をClaudeが書き→OpenAI TTSで音声化し→RSSを更新します。RSSをSpotifyに一度登録すれば、以降は新エピソードが自動で配信されます。

```
ニュース(RSS) ──┐
                ├─► Claudeが対話台本を生成 ─► OpenAI TTSで音声化 ─► docs/episodes/*.mp3
古典(ランダム) ─┘                                                        │
                                                                          ▼
                                          docs/feed.xml (Podcast RSS) ◄── 履歴(state.json)
                                                  │
                                                  ▼
                                       GitHub Pages で公開 ─► Spotifyが巡回取得
```

---

## セットアップ（初回だけ）

### 1. 依存パッケージのインストール
```powershell
cd C:\Users\PC\eichi-radio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. APIキーを設定
`.env.example` を `.env` にコピーして、キーを入れる。

**デフォルトは無料スタック**（`config.yaml` の `script.provider: gemini` / `tts.provider: edge`）:
```
GOOGLE_API_KEY=AIza...   # Gemini無料枠。クレカ不要 → https://aistudio.google.com/apikey
```
- **音声(Edge TTS)はAPIキー不要**。GOOGLE_API_KEY だけで完全無料で動きます。
- 有料の高品質スタックを使う場合のみ、`config.yaml` の provider を `claude`/`openai` にして
  `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` を設定します。

### 3. まず台本だけ試す（課金が少ない / TTSなし）
```powershell
python -m src.main --dry-run
```
対話台本がコンソールに出ればOK。

### 4. 本番実行（音声まで生成）
```powershell
python -m src.main
```
`docs/episodes/ep-YYYYMMDD-HHMM.mp3` と `docs/feed.xml`、`docs/index.html` が作られます。

---

## Spotifyで流せるようにする（公開設定）

Spotifyは音声ファイルを直接アップロードできません。**公開RSSフィードを登録**します。

### A. カバー画像を用意
`docs/cover.jpg` に **正方形（1400×1400〜3000×3000px）** の画像を置く。Spotify/Apple必須です。

### B. GitHub Pages で公開
```powershell
git init
git add .
git commit -m "init eichi-radio"
# GitHubで空のリポジトリ eichi-radio を作ってから:
git remote add origin https://github.com/＜あなた＞/eichi-radio.git
git branch -M main
git push -u origin main
```
GitHubのリポジトリ → **Settings → Pages** → Source を `Deploy from a branch`、Branch を `main` / `/docs` に設定。
数分で `https://＜あなた＞.github.io/eichi-radio/` が公開されます。

### C. config.yaml の base_url を直す
```yaml
base_url: "https://＜あなた＞.github.io/eichi-radio"
```
直したら `python -m src.main --rebuild-feed` でURLを反映。

### D. Spotifyに登録
[Spotify for Creators](https://creators.spotify.com/) → 「Add your podcast」→ RSSフィードURL
`https://＜あなた＞.github.io/eichi-radio/feed.xml` を入力。
審査後、以降は**RSSの新エピソードを自動取得**します（あなたは何もしなくてよい）。

> author / email / title は config.yaml で設定。Spotify登録時の本人確認メールはそのemail宛に届きます。

---

## 毎朝7時に自動化（Windows）

`config.yaml` の `publish.auto_git_push` を `true` にしておくと、生成後に自動でGitHubへpush（=Spotifyへ自動反映）されます。

```powershell
# 毎朝7:00のタスクを登録
.\register_schedule.ps1
```
- 確認: `Get-ScheduledTask -TaskName EichiRadioDeadReckoning`
- 今すぐ手動テスト: `Start-ScheduledTask -TaskName EichiRadioDeadReckoning`
- ログ: `logs\run-YYYYMMDD.log`

> 自動pushを使うには、gitの認証（Git Credential Manager等）が通っている必要があります。

---

## カスタマイズ

| やりたいこと | 場所 |
|---|---|
| 古典を増やす/減らす | `data/classics.json` |
| ニュースのソースを変える | `config.yaml` の `news.feeds` |
| 番組の長さ | `config.yaml` の `script.target_minutes` |
| 声を変える | `config.yaml` の `tts.edge_*_voice`（無料）/ `tts.openai_*_voice`（有料） |
| 台本の作風・演出 | `src/script_gen.py` の `SYSTEM` プロンプト |
| 無料↔有料を切替 | `config.yaml` の `script.provider`（gemini/claude）と `tts.provider`（edge/openai） |

---

## コスト感（1エピソードあたり目安）
- **無料スタック（デフォルト）**: Gemini無料枠 + Edge TTS + GitHub Pages = **¥0**
- 有料スタック（任意）: Claude台本 数円〜十数円 + OpenAI TTS 数十円

## ファイル構成
```
eichi-radio/
├─ config.yaml          # 設定（ここを編集）
├─ .env                 # APIキー（自分で作成・gitに上げない）
├─ data/
│  ├─ classics.json     # 古典リスト
│  └─ state.json        # エピソード履歴（自動生成）
├─ docs/                # ← GitHub Pagesで公開される
│  ├─ feed.xml          # Podcast RSS（Spotifyに登録するURL）
│  ├─ index.html        # エピソード一覧ページ
│  ├─ cover.jpg         # カバー画像（自分で用意）
│  └─ episodes/*.mp3
├─ src/                 # プログラム本体
├─ run_daily.ps1        # 自動実行ラッパー
└─ register_schedule.ps1# 毎朝7時タスク登録
```
誰のためでもなく、完全に自分のために。🚗⛳

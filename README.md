# AceStepGUI (Google Colab向け)

AceStep-1.5 の **OpenRouter互換API** を使い、以下を1画面で扱える Gradio GUI です。

- 生成: `text2music`
- 編集系: `cover` / `repaint` / `lego` / `extract` / `complete`
- 再生: 生成履歴から即座に呼び出して比較再生

この実装は、公式リポジトリ `ace-step/ACE-Step-1.5` の README と API ドキュメントを参照し、サポートされる task_type / 主要パラメータに合わせて構成しています。

## 1. Colab での起動手順

### セル1: 公式リポジトリを参照用にクローン
```bash
git clone https://github.com/ace-step/ACE-Step-1.5
```

### セル2: AceStep APIサーバー起動（例）
> 公式 README の手順に従って ACE-Step をセットアップし、OpenRouter API を起動してください。

### セル3: このGUIを起動
```bash
pip install gradio
python app.py
```

Colab 上では `share=True` で起動されるため、外部URLで UI を開けます。

---

## 2. UI設計方針

### 生成セクション
- API 接続設定（Base URL / API key / model）
- task_type 選択
- Prompt / Lyrics 入力
- `src_audio`, `reference_audio` アップロード
- 公式 API の主要パラメータを「詳細設定」に集約

### プレイヤーセクション
- `Now Playing` で最新生成音源を即再生
- 生成履歴（時刻 + task_type + ファイル名）を一覧化
- 任意履歴をワンクリックで再生・メタ情報確認

---

## 3. 実装済みパラメータ（主要）

- LLM/推論制御: `sample_mode`, `thinking`, `use_format`, `use_cot_caption`, `use_cot_language`
- オーディオ設定: `duration`, `bpm`, `vocal_language`, `instrumental`, `format`, `key_scale`, `time_signature`
- 拡張設定: `guidance_scale`, `batch_size`, `seed`
- 編集設定: `repainting_start`, `repainting_end`, `audio_cover_strength`

---

## 4. 注意

- このリポジトリは **GUIクライアント** です。実際の生成は ACE-Step API サーバー側で行われます。
- `cover/repaint/lego/extract/complete` は `src_audio` が必要です。
- 1回の生成結果を履歴保存してプレイヤーで再生比較できます。

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import request, error

import gradio as gr

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_TYPES = ["text2music", "cover", "repaint", "lego", "extract", "complete"]
AUDIO_FORMATS = ["mp3", "wav", "flac"]
VOCAL_LANGUAGES = [
    "unknown", "en", "zh", "ja", "ko", "es", "fr", "de", "it", "pt", "ru", "ar", "hi", "bn"
]


@dataclass
class TrackRecord:
    id: str
    task_type: str
    created_at: str
    prompt: str
    lyrics: str
    meta_text: str
    audio_path: str


def _to_data_url(audio_path: str) -> Tuple[str, str]:
    ext = Path(audio_path).suffix.lower().replace(".", "") or "mp3"
    mime = "audio/mpeg" if ext == "mp3" else f"audio/{ext}"
    with open(audio_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}", ext


def _api_call(base_url: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except error.URLError as e:
        raise RuntimeError(f"API接続失敗: {e.reason}") from e


def _save_audio_from_response(resp: Dict[str, Any]) -> Tuple[str, str]:
    choice = resp["choices"][0]["message"]
    content = choice.get("content", "")
    audio_url = choice.get("audio", [{}])[0].get("audio_url", {}).get("url")
    if not audio_url or "," not in audio_url:
        raise RuntimeError("APIレスポンスに音声が含まれていません。")

    meta, b64_data = audio_url.split(",", 1)
    ext = "mp3"
    if "audio/" in meta:
        ext = meta.split("audio/")[1].split(";")[0]
    out_name = f"{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
    out_path = OUTPUT_DIR / out_name
    out_path.write_bytes(base64.b64decode(b64_data))
    return str(out_path), content


def _build_messages(prompt: str, src_audio: Optional[str], ref_audio: Optional[str]) -> List[Dict[str, Any]]:
    if not src_audio and not ref_audio:
        return [{"role": "user", "content": prompt.strip()}]

    content = [{"type": "text", "text": prompt.strip()}]
    if src_audio:
        src_data_url, fmt = _to_data_url(src_audio)
        content.append({"type": "input_audio", "input_audio": {"data": src_data_url.split(",", 1)[1], "format": fmt}})
    if ref_audio:
        ref_data_url, fmt = _to_data_url(ref_audio)
        content.append({"type": "input_audio", "input_audio": {"data": ref_data_url.split(",", 1)[1], "format": fmt}})
    return [{"role": "user", "content": content}]


def generate_music(
    base_url: str,
    api_key: str,
    model: str,
    task_type: str,
    prompt: str,
    lyrics: str,
    sample_mode: bool,
    thinking: bool,
    use_format: bool,
    use_cot_caption: bool,
    use_cot_language: bool,
    duration: float,
    bpm: int,
    key_scale: str,
    time_signature: str,
    vocal_language: str,
    instrumental: bool,
    format_name: str,
    guidance_scale: float,
    batch_size: int,
    seed: str,
    repaint_start: float,
    repaint_end: float,
    cover_strength: float,
    src_audio: Optional[str],
    ref_audio: Optional[str],
    history_state: List[Dict[str, Any]],
):
    prompt = prompt.strip()
    if not prompt:
        raise gr.Error("プロンプトは必須です。")

    messages = _build_messages(prompt, src_audio, ref_audio)
    payload = {
        "model": model.strip() or "auto",
        "messages": messages,
        "task_type": task_type,
        "lyrics": lyrics,
        "sample_mode": sample_mode,
        "thinking": thinking,
        "use_format": use_format,
        "use_cot_caption": use_cot_caption,
        "use_cot_language": use_cot_language,
        "guidance_scale": guidance_scale,
        "batch_size": batch_size,
        "audio_cover_strength": cover_strength,
        "repainting_start": repaint_start,
        "repainting_end": repaint_end if repaint_end >= 0 else None,
        "seed": seed.strip() or None,
        "audio_config": {
            "duration": duration if duration > 0 else None,
            "bpm": bpm if bpm > 0 else None,
            "key_scale": key_scale.strip() or None,
            "time_signature": time_signature.strip() or None,
            "vocal_language": vocal_language,
            "instrumental": instrumental,
            "format": format_name,
        },
    }

    resp = _api_call(base_url, api_key, payload)
    audio_path, meta_text = _save_audio_from_response(resp)

    rec = TrackRecord(
        id=uuid.uuid4().hex[:8],
        task_type=task_type,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        prompt=prompt,
        lyrics=lyrics,
        meta_text=meta_text,
        audio_path=audio_path,
    )
    history_state = history_state + [asdict(rec)]
    choices = [f"{r['created_at']} | {r['task_type']} | {Path(r['audio_path']).name}" for r in history_state]
    info = f"✅ 生成完了: {Path(audio_path).name}\n\n{meta_text}"
    return history_state, choices, audio_path, info


def load_history_item(history_state: List[Dict[str, Any]], selection: str):
    if not selection:
        return None, "履歴を選択してください。"
    for r in history_state:
        label = f"{r['created_at']} | {r['task_type']} | {Path(r['audio_path']).name}"
        if label == selection:
            return r["audio_path"], f"### {r['task_type']}\n\n{r['meta_text']}"
    return None, "選択された履歴が見つかりません。"


def clear_history():
    return [], [], None, "履歴をクリアしました。"


def build_ui():
    with gr.Blocks(title="AceStep 1.5 Colab Studio", theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            """
# AceStep 1.5 Colab Studio
公式 OpenRouter互換API を使って、生成・編集・再生を1画面で行うGUIです。
- 生成部: text2music / cover / repaint / lego / extract / complete
- プレイヤー部: 生成履歴を即再生・比較
"""
        )

        history_state = gr.State([])

        with gr.Row():
            with gr.Column(scale=2):
                base_url = gr.Textbox(value="http://127.0.0.1:8002", label="ACE-Step API Base URL")
                api_key = gr.Textbox(value="", label="API Key (必要な場合のみ)", type="password")
                model = gr.Textbox(value="auto", label="Model")

                task_type = gr.Dropdown(TASK_TYPES, value="text2music", label="task_type")
                prompt = gr.Textbox(lines=4, label="Prompt / Instruction")
                lyrics = gr.Textbox(lines=8, label="Lyrics (任意)")

                with gr.Row():
                    src_audio = gr.Audio(type="filepath", label="src_audio (cover/repaint/lego/extract/completeで使用)")
                    ref_audio = gr.Audio(type="filepath", label="reference_audio (任意)")

                with gr.Accordion("詳細設定", open=False):
                    with gr.Row():
                        sample_mode = gr.Checkbox(value=False, label="sample_mode")
                        thinking = gr.Checkbox(value=False, label="thinking")
                        use_format = gr.Checkbox(value=False, label="use_format")
                    with gr.Row():
                        use_cot_caption = gr.Checkbox(value=True, label="use_cot_caption")
                        use_cot_language = gr.Checkbox(value=True, label="use_cot_language")
                        instrumental = gr.Checkbox(value=False, label="instrumental")

                    with gr.Row():
                        duration = gr.Slider(0, 600, value=30, step=1, label="duration")
                        bpm = gr.Slider(0, 220, value=120, step=1, label="bpm")
                        guidance_scale = gr.Slider(1.0, 15.0, value=7.0, step=0.1, label="guidance_scale")

                    with gr.Row():
                        key_scale = gr.Textbox(value="", label="key_scale (例: C major)")
                        time_signature = gr.Textbox(value="", label="time_signature (例: 4/4)")
                        vocal_language = gr.Dropdown(VOCAL_LANGUAGES, value="unknown", label="vocal_language")

                    with gr.Row():
                        batch_size = gr.Slider(1, 8, value=1, step=1, label="batch_size")
                        seed = gr.Textbox(value="", label="seed (例: 42 または 42,123)")
                        format_name = gr.Dropdown(AUDIO_FORMATS, value="mp3", label="format")

                    with gr.Row():
                        repaint_start = gr.Slider(0, 600, value=0, step=0.5, label="repainting_start")
                        repaint_end = gr.Slider(-1, 600, value=-1, step=0.5, label="repainting_end (-1=末尾)")
                        cover_strength = gr.Slider(0.0, 1.0, value=1.0, step=0.05, label="audio_cover_strength")

                generate_btn = gr.Button("🎵 Generate / Edit", variant="primary")

            with gr.Column(scale=1):
                now_playing = gr.Audio(type="filepath", label="Now Playing")
                generation_info = gr.Markdown("生成結果がここに表示されます。")

                history_list = gr.Dropdown([], label="生成履歴")
                with gr.Row():
                    load_btn = gr.Button("履歴を再生")
                    clear_btn = gr.Button("履歴クリア")
                history_meta = gr.Markdown("履歴メタ情報")

        generate_btn.click(
            generate_music,
            inputs=[
                base_url, api_key, model, task_type, prompt, lyrics,
                sample_mode, thinking, use_format, use_cot_caption, use_cot_language,
                duration, bpm, key_scale, time_signature, vocal_language, instrumental, format_name,
                guidance_scale, batch_size, seed, repaint_start, repaint_end, cover_strength,
                src_audio, ref_audio, history_state,
            ],
            outputs=[history_state, history_list, now_playing, generation_info],
        )

        load_btn.click(
            load_history_item,
            inputs=[history_state, history_list],
            outputs=[now_playing, history_meta],
        )

        clear_btn.click(
            clear_history,
            inputs=[],
            outputs=[history_state, history_list, now_playing, history_meta],
        )

    return demo


if __name__ == "__main__":
    app = build_ui()
    share = os.getenv("COLAB_RELEASE_TAG") is not None
    app.launch(share=share, server_name="0.0.0.0", server_port=7860)

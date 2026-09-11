#!/usr/bin/env bash
set -e

echo "[qwen-tts] preloading model weights (first run may take a while)..."

python - <<'PY'
import os
from huggingface_hub import snapshot_download

targets = []
model = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
tokenizer = os.environ.get("TTS_TOKENIZER", "Qwen/Qwen3-TTS-Tokenizer-12Hz")
for name in (model, tokenizer):
    if name and name not in targets:
        targets.append(name)

for name in targets:
    try:
        print(f"[qwen-tts] downloading {name} ...", flush=True)
        snapshot_download(name)
    except Exception as e:
        print(f"[qwen-tts] download failed for {name}: {e}", flush=True)
PY

echo "[qwen-tts] starting HTTP server on 0.0.0.0:8000 ..."
exec uvicorn server:app --host 0.0.0.0 --port 8000

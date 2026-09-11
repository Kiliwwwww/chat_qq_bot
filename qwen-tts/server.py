import io
import os
import logging
import threading
import subprocess

import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("qwen-tts")

MODEL_NAME = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
DEVICE = os.environ.get("TTS_DEVICE", "cuda:0")
DEFAULT_SPEAKER = os.environ.get("TTS_SPEAKER", "Serena")
DEFAULT_LANGUAGE = os.environ.get("TTS_LANGUAGE", "Chinese")
DEFAULT_INSTRUCT = os.environ.get("TTS_INSTRUCT", "")
VOLUME_FILTER = os.environ.get("TTS_VOLUME_FILTER", "loudnorm=I=-16:TP=-1.5:LRA=11")

TEMPERATURE = float(os.environ.get("TTS_TEMPERATURE", "0.6"))
TOP_P = float(os.environ.get("TTS_TOP_P", "0.85"))
TOP_K = int(os.environ.get("TTS_TOP_K", "30"))
SEED = os.environ.get("TTS_SEED", "42")
MAX_NEW_TOKENS = int(os.environ.get("TTS_MAX_NEW_TOKENS", "0"))

app = FastAPI(title="Qwen3-TTS Service")

_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from qwen_tts import Qwen3TTSModel

                logger.info(f"Loading model {MODEL_NAME} on {DEVICE} (first run may download weights)...")
                _model = Qwen3TTSModel.from_pretrained(
                    MODEL_NAME,
                    device_map=DEVICE,
                    dtype=torch.bfloat16,
                )
                logger.info("Model loaded.")
    return _model


class TTSRequest(BaseModel):
    text: str
    speaker: str | None = None
    language: str | None = None
    instruct: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    seed: int | None = None
    max_new_tokens: int | None = None


def wav_to_mp3(wav_bytes: bytes) -> bytes:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", "pipe:0",
    ]
    if VOLUME_FILTER:
        cmd += ["-af", VOLUME_FILTER]
    cmd += ["-f", "mp3", "-b:a", "96k", "pipe:1"]
    proc = subprocess.run(cmd, input=wav_bytes, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="ignore"))
    return proc.stdout


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "loaded": _model is not None,
        "device": DEVICE,
        "default_speaker": DEFAULT_SPEAKER,
    }


@app.get("/speakers")
def speakers():
    try:
        model = get_model()
        return {"speakers": model.get_supported_speakers()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts")
def tts(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    kwargs = {
        "text": text,
        "language": req.language or DEFAULT_LANGUAGE,
        "speaker": req.speaker or DEFAULT_SPEAKER,
    }
    instruct = req.instruct or DEFAULT_INSTRUCT
    if instruct:
        kwargs["instruct"] = instruct

    temperature = TEMPERATURE if req.temperature is None else req.temperature
    top_p = TOP_P if req.top_p is None else req.top_p
    top_k = TOP_K if req.top_k is None else req.top_k
    max_new_tokens = MAX_NEW_TOKENS if req.max_new_tokens is None else req.max_new_tokens
    if temperature and temperature > 0:
        kwargs["temperature"] = temperature
    if top_p and top_p > 0:
        kwargs["top_p"] = top_p
    if top_k and top_k > 0:
        kwargs["top_k"] = top_k
    if max_new_tokens and max_new_tokens > 0:
        kwargs["max_new_tokens"] = max_new_tokens

    seed = req.seed
    if seed is None and SEED != "":
        seed = int(SEED)
    if seed is not None:
        torch.manual_seed(seed)

    try:
        model = get_model()
        wavs, sr = model.generate_custom_voice(**kwargs)
    except Exception as e:
        logger.exception("TTS generation failed")
        raise HTTPException(status_code=500, detail=str(e))

    buf = io.BytesIO()
    sf.write(buf, wavs[0], sr, format="WAV")
    wav_bytes = buf.getvalue()

    try:
        mp3_bytes = wav_to_mp3(wav_bytes)
    except Exception as e:
        logger.error(f"ffmpeg convert failed, returning wav instead: {e}")
        return Response(content=wav_bytes, media_type="audio/wav")

    return Response(content=mp3_bytes, media_type="audio/mpeg")
11
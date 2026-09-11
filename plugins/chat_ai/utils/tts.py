import httpx
from nonebot import get_plugin_config

from ..config import Config
from ..state import db

# 全局语气/口音设置的 DB key（由 /音色 命令写入）
TTS_STYLE_KEY = "tts_style"


async def synthesize(text: str, instruct: str = "") -> bytes:
    """调用 Qwen3-TTS 服务，返回 mp3 音频字节。"""
    config = get_plugin_config(Config)

    # 全局语气/口音（/音色 命令设置）
    style = (db.get_setting(TTS_STYLE_KEY, "") or "").strip()

    if instruct:
        if style:
            # 设置了全局风格时：AI 情绪 + 全局风格，不再强制普通话
            instruct = f"{instruct}，{style}"
        elif "普通话" not in instruct:
            # 未设置全局风格时：默认补充“标准普通话”抑制方言
            instruct = f"{instruct}，请用标准普通话"
    else:
        instruct = style or config.tts_instruct

    payload = {
        "text": text,
        "speaker": config.tts_speaker,
        "language": config.tts_language,
    }
    if instruct:
        payload["instruct"] = instruct

    url = config.tts_base_url.rstrip("/") + "/tts"
    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.content

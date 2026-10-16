"""存表情的收图会话与图片落盘逻辑。

会话只存在内存里：机器人重启后当前收图会结束，需要重新发一次 /存表情。
"""

from __future__ import annotations

import asyncio
import base64
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import httpx
from nonebot import get_plugin_config, logger
from nonebot.adapters.onebot.v11 import MessageSegment

from .config import PROJECT_ROOT, Config

config = get_plugin_config(Config)


def _meme_library():
    """延迟导入奶龙表情库，避免两个插件在加载顺序上互相牵扯"""
    from plugins.meme_sync import meme_library

    return meme_library


def save_root() -> Path:
    """图片保存根目录

    没配 save_meme_root 时直接用奶龙表情库目录，这样存下来的图会自动进表情池，
    /今日奶龙 和开启奶龙后的 AI 跟图都能抽到；配了就存到配的目录。
    """
    configured = (config.save_meme_root or "").strip()
    if not configured:
        try:
            return _meme_library().library_root()
        except Exception as exc:  # 表情库不可用时退回默认目录
            logger.warning(f"[存表情] 读取奶龙表情库目录失败，改用 data/saved_images: {exc}")
            return PROJECT_ROOT / "data" / "saved_images"

    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def is_in_library(directory: Path) -> bool:
    """目录是否在奶龙表情库里面（在里面才需要刷新缓存、也才会被抽图用上）"""
    try:
        root = _meme_library().library_root().resolve()
        return directory.resolve().is_relative_to(root)
    except Exception:
        return False


def library_count() -> int:
    """奶龙表情库当前的图片数量，取不到时返回 0"""
    try:
        return _meme_library().image_count()
    except Exception as exc:
        logger.debug(f"[存表情] 读取奶龙表情库数量失败: {exc}")
        return 0


async def refresh_library_if_needed(directory: Path) -> None:
    """存进奶龙库时刷新一下缓存，新图不用等缓存过期就能被抽到"""
    if not is_in_library(directory):
        return
    try:
        await asyncio.to_thread(_meme_library().refresh)
    except Exception as exc:
        logger.warning(f"[存表情] 刷新奶龙表情库缓存失败: {exc}")

# QQ 图片 CDN 对 UA 比较挑，带上更稳
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

# 目录名里不允许出现的字符（Windows 上会建不出目录）
_INVALID_NAME_CHARS = set('<>:"|?*')

# 指令里没写目录时的默认落点（在保存根目录下）
DEFAULT_FOLDER = "手存"

# 图片魔数 → 后缀，认不出来时按 .jpg 存
_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"BM", ".bmp"),
    (b"\xff\xd8\xff", ".jpg"),
)


@dataclass
class SaveSession:
    """一次收图会话"""

    user_id: int
    directory: Path
    started_at: float = field(default_factory=time.time)
    saved: int = 0
    failed: int = 0
    # 存进奶龙库但超过库上限（meme_max_bytes）的图：存下来了，但不会被抽到
    oversized: int = 0
    last_saved_at: float = 0.0

    @property
    def seconds_since_last_save(self) -> float:
        """距离上一张保存过去多久；一张都还没存过时给一个大值"""
        if not self.last_saved_at:
            return 1e9
        return time.time() - self.last_saved_at


# 进行中的收图会话（管理员只有一个，但按 user_id 存更清楚）
sessions: dict[int, SaveSession] = {}


def get_session(user_id: int) -> SaveSession | None:
    return sessions.get(user_id)


def start_session(user_id: int, directory: Path) -> SaveSession | None:
    """开启（或切换）会话，返回被替换掉的旧会话"""
    old = sessions.pop(user_id, None)
    sessions[user_id] = SaveSession(user_id=user_id, directory=directory)
    return old


def end_session(user_id: int) -> SaveSession | None:
    """结束会话，返回结束前的会话信息"""
    return sessions.pop(user_id, None)


def parse_directory(raw: str) -> tuple[Path | None, str]:
    """把指令里写的目录解析成根目录下的真实路径

    不写目录时落到默认的「手存」目录；写了 `/分类/子分类` 就落到
    `<save_meme_root>/分类/子分类`。顺手丢掉空段和 `..`，避免跳出根目录。
    返回 (目录, 错误信息)。
    """
    parts = [p for p in re.split(r"[/\\]+", (raw or "").strip()) if p not in ("", ".", "..")]
    if not parts:
        parts = [DEFAULT_FOLDER]

    for part in parts:
        if set(part) & _INVALID_NAME_CHARS:
            return None, '目录名不能包含 < > : " | ? * 这些字符'

    directory = save_root().joinpath(*parts)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error(f"[存表情] 创建目录失败 {directory}: {exc}")
        return None, f"创建目录失败：{exc}"
    return directory, ""


def _guess_suffix(content: bytes) -> str:
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    for magic, suffix in _MAGIC:
        if content.startswith(magic):
            return suffix
    return ".jpg"


async def _download(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            return resp.content or None
    except Exception as exc:
        logger.warning(f"[存表情] 图片下载失败 {url}: {exc}")
        return None


def _local_path(raw: str) -> Path | None:
    """把 file:// 或直接给出的本地路径转成 Path"""
    if raw.startswith("file://"):
        candidate = unquote(urlparse(raw).path)
        # Windows 下 file:///C:/x.png 会多一个前导斜杠
        if re.match(r"^/[A-Za-z]:", candidate):
            candidate = candidate[1:]
    else:
        candidate = raw
    return Path(candidate) if candidate else None


async def fetch_image_bytes(segment: MessageSegment) -> bytes | None:
    """取出图片消息段的原始字节：优先按 URL 下载，其次 base64 / 本地路径"""
    data = segment.data or {}

    url = str(data.get("url") or "")
    if url.startswith("http"):
        content = await _download(url)
        if content:
            return content

    raw = str(data.get("file") or url or "")
    if raw.startswith("base64://"):
        try:
            return base64.b64decode(raw[len("base64://") :])
        except Exception as exc:
            logger.warning(f"[存表情] base64 图片解析失败: {exc}")
            return None

    path = _local_path(raw)
    if path and path.is_file():
        try:
            return await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            logger.warning(f"[存表情] 读取本地图片失败 {path}: {exc}")
    return None


async def save_image(segment: MessageSegment, session: SaveSession) -> bool:
    """把一张图片存进会话目录，成功返回 True"""
    content = await fetch_image_bytes(segment)
    if not content:
        session.failed += 1
        return False

    limit = max(0, int(config.save_meme_max_bytes or 0))
    if limit and len(content) > limit:
        logger.warning(
            f"[存表情] 跳过超过 {limit / 1024 / 1024:.0f}MB 的图片（{len(content)} 字节）"
        )
        session.failed += 1
        return False

    name = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}{_guess_suffix(content)}"
    target = session.directory / name
    try:
        await asyncio.to_thread(target.write_bytes, content)
    except OSError as exc:
        logger.error(f"[存表情] 写入失败 {target}: {exc}")
        session.failed += 1
        return False

    session.saved += 1
    session.last_saved_at = time.time()

    # 存进奶龙库的图还得过库自己的体积上限，超了的存得下来但抽不到
    if is_in_library(session.directory):
        try:
            limit_bytes = _meme_library().max_bytes()
        except Exception:
            limit_bytes = 0
        if limit_bytes and len(content) > limit_bytes:
            session.oversized += 1
            logger.warning(
                f"[存表情] {target.name} 超过奶龙库上限 "
                f"{limit_bytes / 1024 / 1024:.0f}MB，不会被 /今日奶龙 抽到"
            )

    logger.info(f"[存表情] 已保存 {target}（{len(content)} 字节）")
    return True

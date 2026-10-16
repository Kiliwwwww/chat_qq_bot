"""本地奶龙表情包库：随机取图 + 群开关状态。

图片来自 plugins/meme_sync/naihub.py 同步下来的目录，这里只负责挑选与发送用的段落构造。
群开关状态存在 data/meme_sync/groups.json 里，配合 .env 的 meme_group_ids 生效：
    最终是否开启 = 群号在 meme_group_ids 中（或已被 /开启奶龙 打开），且没有被 /关闭奶龙 关掉。
"""

from __future__ import annotations

import asyncio
import json
import random
import threading
import time
from pathlib import Path

from nonebot import get_plugin_config, logger
from nonebot.adapters.onebot.v11 import MessageSegment

from .config import Config

config = get_plugin_config(Config)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# 图片列表缓存，避免每次都遍历目录
_CACHE_TTL = 60.0
_cache_lock = threading.Lock()
_cache_paths: list[Path] = []
_cache_at: float = 0.0

# 上一次发出的图片，尽量避免连着发同一张
_last_picked: Path | None = None

_state_lock = threading.Lock()
_state_cache: dict[str, list[int]] | None = None


def _out_dir() -> Path:
    return Path(config.meme_sync_out_dir)


def max_bytes() -> int:
    """单张表情包的体积上限，0 表示不限制。"""
    try:
        return max(0, int(config.meme_max_bytes))
    except (TypeError, ValueError):
        return 0


def _scan() -> list[Path]:
    root = _out_dir()
    if not root.exists():
        return []
    limit = max_bytes()
    paths: list[Path] = []
    skipped = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            if limit and path.stat().st_size > limit:
                skipped += 1
                continue
        except OSError:
            continue
        paths.append(path)
    if skipped:
        logger.debug(f"[表情包同步] 跳过 {skipped} 张超过 {limit / 1024 / 1024:.0f} MB 的图片")
    return sorted(paths)


def refresh() -> int:
    """重新扫描图片目录，返回当前图片数量。"""
    global _cache_paths, _cache_at
    paths = _scan()
    with _cache_lock:
        _cache_paths = paths
        _cache_at = time.time()
    return len(paths)


def all_images() -> list[Path]:
    with _cache_lock:
        if _cache_paths and time.time() - _cache_at < _CACHE_TTL:
            return _cache_paths
    refresh()
    with _cache_lock:
        return _cache_paths


def image_count() -> int:
    return len(all_images())


def pick_random() -> Path | None:
    """随机挑一张图片，库里为空时返回 None。"""
    global _last_picked
    paths = all_images()
    if not paths:
        return None
    choice = random.choice(paths)
    if len(paths) > 1:
        for _ in range(3):
            if choice != _last_picked:
                break
            choice = random.choice(paths)
    _last_picked = choice
    return choice


async def random_image_segment() -> tuple[MessageSegment, str] | None:
    """随机取一张表情包，返回 (消息段落, 文件名)；库为空或读取失败时返回 None。

    图片以 base64 内嵌发送，不能传本地路径：机器人在容器里，QQ 框架在容器外，
    对方按容器内的路径找不到文件，会导致整条消息发送失败。
    """
    path = pick_random()
    if path is None:
        return None
    try:
        # 大图 base64 编码有一定耗时，放到线程里做，别卡住事件循环
        data = await asyncio.to_thread(path.read_bytes)
    except OSError as exc:
        logger.warning(f"[表情包同步] 表情包读取失败 {path}: {exc}")
        return None
    return MessageSegment.image(data), path.name


# --------------------------------------------------------------------------
# 群开关
# --------------------------------------------------------------------------

def _state_file() -> Path:
    return Path(config.meme_groups_file)


def _load_state() -> dict[str, list[int]]:
    global _state_cache
    with _state_lock:
        if _state_cache is not None:
            return _state_cache
        state: dict[str, list[int]] = {"enabled": [], "disabled": []}
        try:
            raw = json.loads(_state_file().read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in ("enabled", "disabled"):
                    values = raw.get(key) or []
                    if isinstance(values, list):
                        state[key] = [int(v) for v in values]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as exc:
            logger.warning(f"[表情包同步] 群开关文件读取失败，按未配置处理：{exc}")
        _state_cache = state
        return state


def _save_state(state: dict[str, list[int]]) -> None:
    global _state_cache
    path = _state_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error(f"[表情包同步] 群开关保存失败：{exc}")
        return
    with _state_lock:
        _state_cache = state


def is_group_enabled(group_id: int) -> bool:
    """判断该群是否开启了奶龙表情包功能。"""
    state = _load_state()
    if group_id in state["disabled"]:
        return False
    if group_id in state["enabled"]:
        return True
    return group_id in set(config.meme_group_ids or [])


def set_group_enabled(group_id: int, enabled: bool) -> None:
    """打开/关闭某个群的奶龙表情包功能，结果持久化到本地文件。"""
    current = _load_state()
    state = {"enabled": list(current["enabled"]), "disabled": list(current["disabled"])}
    keep, drop = ("enabled", "disabled") if enabled else ("disabled", "enabled")
    if group_id not in state[keep]:
        state[keep].append(group_id)
    if group_id in state[drop]:
        state[drop].remove(group_id)
    _save_state(state)


# --------------------------------------------------------------------------
# 供 chat_ai 读取的概率配置
# --------------------------------------------------------------------------

def attach_chance() -> float:
    """AI 回复附带表情包的概率（1.0 表示每条都带）。"""
    return max(0.0, min(1.0, float(config.meme_attach_chance)))


def standalone_chance() -> float:
    """回复群友后，额外单独发一张表情包的概率。"""
    return max(0.0, min(1.0, float(config.meme_standalone_chance)))


def bubble_attach_enabled() -> bool:
    """主动冒泡消息是否也附带表情包。"""
    return bool(config.meme_bubble_attach)


def reply_meme_chance() -> float:
    """AI 回复结束后，单独跟一条图片消息的概率。

    attach 与 standalone 描述的都是「回复后跟一张图」这件事，取两者较大值，
    避免两条概率各自命中时在同一次回复后连发两张图。
    """
    return max(attach_chance(), standalone_chance())

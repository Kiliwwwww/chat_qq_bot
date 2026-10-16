"""奶-hub 表情包每日自动同步。

每天 0 点（可配置）自动拉取站点最新表情包，已下载过的文件自动跳过；
管理员也可以用 /同步表情包 手动触发一次。
开启功能的群里，AI 回复结束后会再单独跟一条随机表情包消息（两条独立消息），
详见 meme_library.py 与 chat_ai。
"""

from __future__ import annotations

import asyncio
from zoneinfo import ZoneInfo

from nonebot import get_plugin_config, logger, on_command, require
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from . import naihub  # noqa: E402
from . import meme_library  # noqa: E402
from .config import Config  # noqa: E402

config = get_plugin_config(Config)
timezone = ZoneInfo(config.meme_sync_timezone)

# 定时任务与手动命令共用一个锁，避免同时跑两份
_sync_lock = asyncio.Lock()


def _log(level: str, message: str) -> None:
    if level == "error":
        logger.warning(f"[表情包同步] {message}")
    elif level == "detail":
        logger.debug(f"[表情包同步] {message}")
    else:
        logger.info(f"[表情包同步] {message}")


def _run_sync() -> dict:
    return naihub.sync(
        config.meme_sync_out_dir,
        chars=config.meme_sync_chars,
        subs=config.meme_sync_subs,
        workers=config.meme_sync_workers,
        timeout=config.meme_sync_timeout,
        route=config.meme_sync_route,
        log=_log,
    )


async def _sync_now() -> dict:
    """在线程里执行同步，避免阻塞事件循环。"""
    async with _sync_lock:
        result = await asyncio.to_thread(_run_sync)
    # 新下载的图片立刻可用，不用等缓存过期
    meme_library.refresh()
    return result


def _summary_text(result: dict) -> str:
    return (
        f"新增 {result['ok']} 张（{result['bytes'] / 1024 / 1024:.1f} MB），"
        f"跳过 {result['skip']} 张，失败 {result['fail']} 张，"
        f"耗时 {result['elapsed']} 秒"
    )


@scheduler.scheduled_job(
    "cron",
    hour=config.meme_sync_hour,
    minute=config.meme_sync_minute,
    timezone=timezone,
    id="meme_sync_daily",
    coalesce=True,
    max_instances=1,
    misfire_grace_time=3600,
)
async def meme_sync_daily() -> None:
    """每天定时同步奶-hub 表情包，已存在的文件会跳过。"""
    if not config.meme_sync_enabled:
        return
    logger.info(f"开始执行表情包同步（{config.meme_sync_timezone} "
                f"{config.meme_sync_hour:02d}:{config.meme_sync_minute:02d}）")
    try:
        result = await _sync_now()
    except Exception as exc:  # noqa: BLE001 - 定时任务不能把异常抛给调度器
        logger.error(f"表情包同步执行失败：{exc}")
        return
    logger.info(f"表情包同步完成：{_summary_text(result)}")
    if result["fail"]:
        for item in result["failures"][:5]:
            logger.warning(f"  失败：{item['title']}（{item['error']}）")


sync_cmd = on_command("同步表情包", aliases={"表情包同步"}, priority=15, block=False)


@sync_cmd.handle()
async def _handle_sync_cmd(event: MessageEvent) -> None:
    if event.user_id != config.admin_qq:
        return
    await sync_cmd.send("开始同步奶-hub 表情包，稍等一下…")
    try:
        result = await _sync_now()
    except Exception as exc:  # noqa: BLE001
        await sync_cmd.finish(f"同步失败：{exc}")
    if result["total"] == 0:
        await sync_cmd.finish("没有获取到图片清单，请检查网络或筛选配置。")
    await sync_cmd.finish(f"同步完成：{_summary_text(result)}")


meme_on_cmd = on_command("开启奶龙", priority=5, block=True)
meme_off_cmd = on_command("关闭奶龙", priority=5, block=True)
meme_status_cmd = on_command("奶龙状态", priority=5, block=True)


def _group_scope(event: MessageEvent) -> int | None:
    """取出群号；非管理员或非群聊返回 None。"""
    if event.user_id != config.admin_qq:
        return None
    if not isinstance(event, GroupMessageEvent):
        return None
    return event.group_id


@meme_on_cmd.handle()
async def _handle_meme_on(event: MessageEvent) -> None:
    group_id = _group_scope(event)
    if group_id is None:
        return
    meme_library.set_group_enabled(group_id, True)
    count = meme_library.image_count()
    logger.info(f"群 {group_id} 开启奶龙表情包功能，表情库 {count} 张")
    if count:
        await meme_on_cmd.finish(f"本群已开启奶龙表情包（表情库 {count} 张），AI 回复会带上表情包啦")
    await meme_on_cmd.finish("本群已开启奶龙表情包，但表情库还是空的，等 0 点自动同步后再试试")


@meme_off_cmd.handle()
async def _handle_meme_off(event: MessageEvent) -> None:
    group_id = _group_scope(event)
    if group_id is None:
        return
    meme_library.set_group_enabled(group_id, False)
    logger.info(f"群 {group_id} 关闭奶龙表情包功能")
    await meme_off_cmd.finish("本群已关闭奶龙表情包")


@meme_status_cmd.handle()
async def _handle_meme_status(event: MessageEvent) -> None:
    group_id = _group_scope(event)
    if group_id is None:
        return
    enabled = meme_library.is_group_enabled(group_id)
    count = meme_library.image_count()
    state_text = "已开启" if enabled else "未开启"
    await meme_status_cmd.finish(
        f"奶龙表情包：{state_text}；表情库 {count} 张；"
        f"每次回复后单独发一张的概率 {meme_library.reply_meme_chance():.0%}"
    )

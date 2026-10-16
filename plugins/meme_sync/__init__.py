"""奶-hub 表情包每日自动同步。

每天 0 点（可配置）自动拉取站点最新表情包，已下载过的文件自动跳过；
管理员也可以用 /同步表情包 手动触发一次。
"""

from __future__ import annotations

import asyncio
from zoneinfo import ZoneInfo

from nonebot import get_plugin_config, logger, on_command, require
from nonebot.adapters.onebot.v11 import MessageEvent

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from . import naihub  # noqa: E402
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
        return await asyncio.to_thread(_run_sync)


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

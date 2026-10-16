from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from nonebot import get_driver, get_plugin_config, logger, on_command
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    Message,
    MessageSegment,
)

from .config import Config
from .database import LotteryDatabase
from .gif_renderer import LotteryGifRenderer
from .lottery_engine import LotteryEngine


config = get_plugin_config(Config)
timezone = ZoneInfo(config.lottery_timezone)
database = LotteryDatabase(config.lottery_data_dir / "lottery.db")
engine = LotteryEngine(config.lottery_items_path)
renderer = LotteryGifRenderer(
    html_path=config.lottery_html_path,
    gif_duration_ms=config.lottery_gif_duration_ms,
    fps=config.lottery_gif_fps,
    max_width=config.lottery_gif_max_width,
    timeout_ms=config.lottery_browser_timeout_ms,
    browser_channel=config.lottery_browser_channel,
)

draw_cmd = on_command("开箱", priority=5, block=True)
today_draws_cmd = on_command(
    "今日开箱",
    aliases={"开箱记录"},
    priority=5,
    block=True,
)

driver = get_driver()


def _now() -> datetime:
    return datetime.now(timezone)


def _price_text(price: int | float) -> str:
    return f"{int(price):,}"


def _gif_path(draw_date: str, user_id: int, record_id: int) -> Path:
    return (
        config.lottery_data_dir
        / "gifs"
        / draw_date
        / str(user_id)
        / f"draw_{record_id}.gif"
    )


async def _read_base64(path: Path) -> str:
    def read_file() -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    return await asyncio.to_thread(read_file)


@driver.on_startup
async def initialize_lottery() -> None:
    await database.initialize()
    try:
        cleaned = await database.cleanup_stale_pending(_now() - timedelta(minutes=15))
        if cleaned:
            logger.warning(f"开箱插件清理了 {cleaned} 条中断的抽奖记录")
    except Exception as error:
        logger.error(f"清理中断的开箱记录失败: {error}")

    try:
        await renderer.start()
        logger.info("开箱动画渲染服务启动成功")
    except Exception as error:
        logger.error(f"开箱动画渲染服务启动失败: {error}")


@driver.on_shutdown
async def close_lottery_renderer() -> None:
    await renderer.close()


@draw_cmd.handle()
async def handle_draw(event: GroupMessageEvent) -> None:
    now = _now()
    draw_date = now.date().isoformat()
    user_id = event.user_id

    last_item = await database.get_last_completed_item(user_id)
    item = engine.pick_result(last_item)
    record = await database.reserve_draw(
        user_id=user_id,
        group_id=event.group_id,
        draw_date=draw_date,
        created_at=now.isoformat(),
        item=item.as_dict(),
        daily_limit=config.lottery_daily_limit,
    )

    if record is None:
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await draw_cmd.finish(
            MessageSegment.reply(event.message_id)
            + MessageSegment.text(
                f"今天的 {config.lottery_daily_limit} 次开箱机会已经用完了。"
                f"\n明天 {tomorrow.strftime('%H:%M')} 会重新恢复。"
            )
        )

    await draw_cmd.send(
        MessageSegment.reply(event.message_id)
        + MessageSegment.text("📦 正在开启补给箱，请稍候……")
    )

    gif_path = _gif_path(draw_date, user_id, int(record["id"]))
    try:
        await renderer.render(item.item_name, gif_path)
        completed = await database.complete_draw(
            int(record["id"]), str(gif_path), _now().isoformat()
        )
        if not completed:
            raise RuntimeError("保存抽奖结果失败")
    except Exception as error:
        logger.exception(f"开箱动画生成失败 record_id={record['id']}")
        await database.release_draw(int(record["id"]), str(error))
        try:
            await asyncio.to_thread(gif_path.unlink, True)
        except OSError:
            pass
        await draw_cmd.finish(
            MessageSegment.reply(event.message_id)
            + MessageSegment.text("开箱失败了，本次没有扣除次数，请稍后再试~")
        )

    image_base64 = await _read_base64(gif_path)
    message = Message()
    message += MessageSegment.reply(event.message_id)
    message += MessageSegment.image(f"base64://{image_base64}")
    message += MessageSegment.text(
        f"\n🎉 获得 [{item.rarity}] {item.item_name}"
        f"\n💰 价值：{_price_text(item.price)} 哈夫币"
        f"\n今日剩余次数：{record['remaining']}/{config.lottery_daily_limit}"
    )
    await draw_cmd.finish(message)


@today_draws_cmd.handle()
async def handle_today_draws(event: GroupMessageEvent) -> None:
    now = _now()
    draw_date = now.date().isoformat()
    records = await database.get_today_draws(event.user_id, draw_date)

    sender_name = event.sender.card or event.sender.nickname or str(event.user_id)
    if not records:
        await today_draws_cmd.finish(
            MessageSegment.reply(event.message_id)
            + MessageSegment.text(
                f"{sender_name} 今天还没有抽到物品。\n"
                f"发送 /开箱 参与抽奖，每天最多 {config.lottery_daily_limit} 次。"
            )
        )

    total_value = sum(int(record["price"]) for record in records)
    lines = [
        f"{sender_name} 今日开箱记录"
        f"（{len(records)}/{config.lottery_daily_limit}）"
    ]
    for index, record in enumerate(records, start=1):
        created_at = datetime.fromisoformat(record["created_at"]).astimezone(timezone)
        lines.append(
            f"{index}. [{record['rarity']}] {record['item_name']}"
            f" · {_price_text(record['price'])} 哈夫币"
            f" · {created_at.strftime('%H:%M')}"
        )
    lines.append(f"今日累计价值：{_price_text(total_value)} 哈夫币")

    await today_draws_cmd.finish(
        MessageSegment.reply(event.message_id)
        + MessageSegment.text("\n".join(lines))
    )

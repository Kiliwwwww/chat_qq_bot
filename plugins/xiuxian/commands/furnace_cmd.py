"""炉鼎指令。"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from ..state import db
from ..services import furnace as furnace_svc
from .helpers import require_game

capture_cmd = on_command("抓捕", priority=5, block=True)
furnace_cmd = on_command("炉鼎", aliases={"我的炉鼎"}, priority=5, block=True)
escape_cmd = on_command("挣脱", aliases={"挣脱束缚"}, priority=5, block=True)


def _extract_at_target(args: Message) -> int:
    """从消息中提取被 @ 的用户 QQ 号"""
    for seg in args:
        if seg.type == "at":
            try:
                return int(seg.data.get("qq", 0))
            except (ValueError, TypeError):
                return 0
    return 0


@capture_cmd.handle()
async def handle_capture(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = await require_game(capture_cmd, event)

    target_id = _extract_at_target(args)
    if not target_id:
        await capture_cmd.finish("请 @ 一个闭关中的玩家作为抓捕目标，如：抓捕 @某某")

    # 检查目标是否在本群有角色
    target = db.get_player(group_id, target_id)
    if not target:
        await capture_cmd.finish("对方没有修仙角色，无法抓捕")

    result = furnace_svc.capture(group_id, event.user_id, target_id)
    if not result["ok"]:
        await capture_cmd.finish(result["text"])

    from .helpers import get_nickname
    target_name = await get_nickname(bot, group_id, target_id)
    await capture_cmd.finish(
        f"{result['text']}\n"
        f"🎯 你已将 {target_name} 收为炉鼎，修炼加速 10%！\n"
        f"💡 对方可发送「挣脱」尝试反抗，高气运者可能触发天命觉醒"
    )


@furnace_cmd.handle()
async def handle_furnace(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(furnace_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        await furnace_cmd.finish("你还没有修仙角色")

    # 检查自己是否被俘
    captured = db.get_furnace_by_target(group_id, event.user_id)
    text_parts = []
    if captured:
        owner = db.get_player(group_id, captured["owner_id"])
        owner_name = owner["name"] if owner else str(captured["owner_id"])
        text_parts.append(f"⚠️ 你正被 {owner_name} 作为炉鼎！（发送「挣脱」反抗）")
    text_parts.append(furnace_svc.list_furnaces(group_id, event.user_id))
    await furnace_cmd.finish("\n".join(text_parts))


@escape_cmd.handle()
async def handle_escape(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(escape_cmd, event)

    result = await furnace_svc.escape(group_id, event.user_id)
    await escape_cmd.finish(result["text"])

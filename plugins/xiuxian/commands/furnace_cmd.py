"""弟子指令。"""

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from ..state import db
from ..services import furnace as furnace_svc
from .helpers import require_game, xiuxian_command, reply_finish

capture_cmd = xiuxian_command("收徒", priority=5, block=True)
furnace_cmd = xiuxian_command("弟子", aliases={"我的弟子"}, priority=5, block=True)
escape_cmd = xiuxian_command("叛门", aliases={"叛出师门"}, priority=5, block=True)
release_cmd = xiuxian_command("逐出", priority=5, block=True)
xiuxiu_cmd = xiuxian_command("传功", priority=5, block=True)


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
        await reply_finish(capture_cmd, event, "请 @ 一个闭关中的玩家作为收徒目标，如：收徒 @某某")

    # 检查目标是否在本群有角色
    target = db.get_player(group_id, target_id)
    if not target:
        await reply_finish(capture_cmd, event, "对方没有修仙角色，无法收徒")

    result = furnace_svc.capture(group_id, event.user_id, target_id)
    if not result["ok"]:
        await reply_finish(capture_cmd, event, result["text"])

    from .helpers import get_nickname
    target_name = await get_nickname(bot, group_id, target_id)
    await reply_finish(capture_cmd, event, 
        f"{result['text']}\n"
        f"🎯 你已将 {target_name} 收为弟子，修炼加速 10%！\n"
        f"💡 对方可发送「叛门」尝试脱离师门，高气运者可能触发天命觉醒"
    )


@furnace_cmd.handle()
async def handle_furnace(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(furnace_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        await reply_finish(furnace_cmd, event, "你还没有修仙角色")

    # 检查自己是否已被收为弟子
    captured = db.get_furnace_by_target(group_id, event.user_id)
    text_parts = []
    if captured:
        owner = db.get_player(group_id, captured["owner_id"])
        owner_name = owner["name"] if owner else str(captured["owner_id"])
        text_parts.append(f"⚠️ 你已拜 {owner_name} 为师！（发送「叛门」脱离师门）")
    text_parts.append(furnace_svc.list_furnaces(group_id, event.user_id))
    await reply_finish(furnace_cmd, event, "\n".join(text_parts))


@escape_cmd.handle()
async def handle_escape(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(escape_cmd, event)

    result = await furnace_svc.escape(group_id, event.user_id)
    await reply_finish(escape_cmd, event, result["text"])


@release_cmd.handle()
async def handle_release(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(release_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await reply_finish(release_cmd, event, "请指定弟子编号，如：逐出 1（发送「弟子」查看编号）")
    result = furnace_svc.release_furnace(group_id, event.user_id, int(arg))
    await reply_finish(release_cmd, event, result["text"])


@xiuxiu_cmd.handle()
async def handle_xiuxiu(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(xiuxiu_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await reply_finish(xiuxiu_cmd, event, "请指定弟子编号，如：传功 1（发送「弟子」查看编号）")
    result = furnace_svc.xiuxiu(group_id, event.user_id, int(arg))
    await reply_finish(xiuxiu_cmd, event, result["text"])

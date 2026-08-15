"""蛊修指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..state import db
from ..services import gu as gu_svc
from .helpers import get_nickname, require_game, xiuxian_command, reply_finish

gu_create_cmd = xiuxian_command("我要修蛊", priority=5, block=True)
gu_status_cmd = xiuxian_command("蛊修", aliases={"蛊修状态", "蛊修面板"}, priority=5, block=True)
gu_list_cmd = xiuxian_command("蛊虫", aliases={"我的蛊虫"}, priority=5, block=True)
gu_seek_cmd = xiuxian_command("寻蛊", priority=5, block=True)
gu_feed_cmd = xiuxian_command("蛊养", aliases={"喂蛊"}, priority=5, block=True)
gu_refine_cmd = xiuxian_command("炼蛊", priority=5, block=True)
gu_caigi_cmd = xiuxian_command("采气", priority=5, block=True)
gu_use_cmd = xiuxian_command("用蛊", priority=5, block=True)
gu_yun_cmd = xiuxian_command("运蛊", aliases={"杀招搭配"}, priority=5, block=True)
gu_kill_cmd = xiuxian_command("杀招", priority=5, block=True)
gu_break_cmd = xiuxian_command("蛊修突破", aliases={"渡劫"}, priority=5, block=True)


def _require_gu(player) -> str:
    """校验玩家是蛊修，非蛊修返回提示文本（蛊修则返回空串）"""
    if not player or player.get("cultivation_path") != "gu":
        return "你不是蛊修，发送「我要修蛊」踏上蛊修之路"
    return ""


@gu_create_cmd.handle()
async def handle_gu_create(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_create_cmd, event)
    name = await get_nickname(bot, group_id, event.user_id)
    result = gu_svc.create_gu_character(group_id, event.user_id, name)
    await reply_finish(gu_create_cmd, event, result["text"])


@gu_status_cmd.handle()
async def handle_gu_status(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_status_cmd, event)
    await reply_finish(gu_status_cmd, event, gu_svc.format_gu_status(group_id, event.user_id))


@gu_list_cmd.handle()
async def handle_gu_list(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_list_cmd, event)
    await reply_finish(gu_list_cmd, event, gu_svc.format_gu_status(group_id, event.user_id))


@gu_seek_cmd.handle()
async def handle_gu_seek(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_seek_cmd, event)
    player = db.get_player(group_id, event.user_id)
    block = _require_gu(player)
    if block:
        await reply_finish(gu_seek_cmd, event, block)
    result = await gu_svc.seek_gu(group_id, event.user_id)
    await reply_finish(gu_seek_cmd, event, result["text"])


@gu_feed_cmd.handle()
async def handle_gu_feed(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_feed_cmd, event)
    player = db.get_player(group_id, event.user_id)
    block = _require_gu(player)
    if block:
        await reply_finish(gu_feed_cmd, event, block)
    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await reply_finish(gu_feed_cmd, event, "请指定蛊虫编号，如：蛊养 1")
    result = gu_svc.feed_gu(group_id, event.user_id, int(arg))
    await reply_finish(gu_feed_cmd, event, result["text"])


@gu_refine_cmd.handle()
async def handle_gu_refine(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_refine_cmd, event)
    player = db.get_player(group_id, event.user_id)
    block = _require_gu(player)
    if block:
        await reply_finish(gu_refine_cmd, event, block)
    parts = args.extract_plain_text().strip().split()
    if len(parts) < 2:
        await reply_finish(gu_refine_cmd, event, "请指定至少 2 只蛊虫编号，如：炼蛊 1 2 3")
    try:
        indexes = [int(p) for p in parts]
    except ValueError:
        await reply_finish(gu_refine_cmd, event, "蛊虫编号必须是数字")
    result = gu_svc.refine_gu(group_id, event.user_id, indexes)
    await reply_finish(gu_refine_cmd, event, result["text"])


@gu_caigi_cmd.handle()
async def handle_gu_caigi(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_caigi_cmd, event)
    player = db.get_player(group_id, event.user_id)
    block = _require_gu(player)
    if block:
        await reply_finish(gu_caigi_cmd, event, block)
    location = args.extract_plain_text().strip() or "洞府"
    result = await gu_svc.caigi(group_id, event.user_id, location)
    await reply_finish(gu_caigi_cmd, event, result["text"])


@gu_use_cmd.handle()
async def handle_gu_use(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_use_cmd, event)
    player = db.get_player(group_id, event.user_id)
    block = _require_gu(player)
    if block:
        await reply_finish(gu_use_cmd, event, block)
    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await reply_finish(gu_use_cmd, event, "请指定蛊虫编号，如：用蛊 1")
    result = gu_svc.use_gu(group_id, event.user_id, int(arg))
    await reply_finish(gu_use_cmd, event, result["text"])


@gu_yun_cmd.handle()
async def handle_gu_yun(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_yun_cmd, event)
    await reply_finish(gu_yun_cmd, event, gu_svc.list_kills(group_id, event.user_id))


@gu_kill_cmd.handle()
async def handle_gu_kill(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_kill_cmd, event)
    player = db.get_player(group_id, event.user_id)
    block = _require_gu(player)
    if block:
        await reply_finish(gu_kill_cmd, event, block)
    kill_id = args.extract_plain_text().strip()
    if not kill_id:
        await reply_finish(gu_kill_cmd, event, "请指定杀招，如：杀招 kuanggong（发送「运蛊」查看）")
    result = gu_svc.use_kill(group_id, event.user_id, kill_id)
    await reply_finish(gu_kill_cmd, event, result["text"])


@gu_break_cmd.handle()
async def handle_gu_break(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gu_break_cmd, event)
    player = db.get_player(group_id, event.user_id)
    block = _require_gu(player)
    if block:
        await reply_finish(gu_break_cmd, event, block)
    arg_text = args.extract_plain_text().strip()
    use_pill = "破境丹" in arg_text or "用" in arg_text
    result = gu_svc.gu_breakthrough(group_id, event.user_id, use_pill=use_pill)
    await reply_finish(gu_break_cmd, event, result["text"])

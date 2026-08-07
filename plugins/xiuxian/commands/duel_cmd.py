"""生死台指令。"""

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from ..services import duel as duel_svc
from .helpers import require_game, xiuxian_command, reply_finish

# 发起生死台挑战
duel_challenge_cmd = xiuxian_command("开启生死台", aliases={"生死台挑战"}, priority=5, block=True)
# 应战
duel_accept_cmd = xiuxian_command("同意生死台", aliases={"接受生死台", "应战"}, priority=5, block=True)


def _extract_at_target(args: Message) -> int:
    """从消息中提取被 @ 的用户 QQ 号"""
    for seg in args:
        if seg.type == "at":
            try:
                return int(seg.data.get("qq", 0))
            except (ValueError, TypeError):
                return 0
    return 0


@duel_challenge_cmd.handle()
async def handle_duel_challenge(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = await require_game(duel_challenge_cmd, event)

    target_id = _extract_at_target(args)
    if not target_id:
        await reply_finish(duel_challenge_cmd, event, "请 @ 一个玩家作为对手，如：开启生死台 @某某")

    result = await duel_svc.challenge(group_id, event.user_id, target_id)
    await reply_finish(duel_challenge_cmd, event, result["text"])


@duel_accept_cmd.handle()
async def handle_duel_accept(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(duel_accept_cmd, event)
    result = await duel_svc.accept(group_id, event.user_id)
    await reply_finish(duel_accept_cmd, event, result["text"])

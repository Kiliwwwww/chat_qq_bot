"""大乱斗与 PK 指令。"""

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from ..state import db
from ..services import battle as battle_svc
from ..services import combat as combat_svc
from .helpers import get_nickname, require_game, xiuxian_command, reply_finish

# 报名大乱斗
signup_cmd = xiuxian_command("报名大乱斗", aliases={"大乱斗报名"}, priority=5, block=True)
# 大乱斗状态
battle_status_cmd = xiuxian_command("大乱斗", aliases={"大乱斗状态"}, priority=5, block=True)
# 攻击/挑战玩家
pk_cmd = xiuxian_command("攻击", aliases={"挑战", "PK"}, priority=5, block=True)


def _extract_at_target(args: Message) -> int:
    """从消息中提取被 @ 的用户 QQ 号"""
    for seg in args:
        if seg.type == "at":
            try:
                return int(seg.data.get("qq", 0))
            except (ValueError, TypeError):
                return 0
    return 0


@signup_cmd.handle()
async def handle_signup(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(signup_cmd, event)

    # 归西复活检查
    player = db.get_player(group_id, event.user_id)
    if player:
        combat_svc.try_revive(group_id, event.user_id)

    result = battle_svc.signup(group_id, event.user_id)
    await reply_finish(signup_cmd, event, result["text"])


@battle_status_cmd.handle()
async def handle_battle_status(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(battle_status_cmd, event)
    await reply_finish(battle_status_cmd, event, battle_svc.format_signup_status(group_id))


@pk_cmd.handle()
async def handle_pk(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = await require_game(pk_cmd, event)

    target_id = _extract_at_target(args)
    if not target_id:
        await reply_finish(pk_cmd, event, "请 @ 一个玩家作为挑战目标，如：攻击 @某某")

    if target_id == event.user_id:
        await reply_finish(pk_cmd, event, "不能挑战自己")

    if not db.get_player(group_id, target_id):
        await reply_finish(pk_cmd, event, "对方没有修仙角色，无法挑战")

    # 归西复活检查
    attacker = db.get_player(group_id, event.user_id)
    if attacker:
        combat_svc.try_revive(group_id, event.user_id)

    result = combat_svc.pk(group_id, event.user_id, target_id)
    await reply_finish(pk_cmd, event, result["text"])

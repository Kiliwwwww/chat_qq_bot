"""世界 Boss 指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..services import boss as boss_svc
from .helpers import require_game, xiuxian_command, reply_finish

boss_attack_cmd = xiuxian_command("讨伐boss", aliases={"讨伐", "打boss"}, priority=5, block=True)
boss_status_cmd = xiuxian_command("boss状态", aliases={"boss", "世界boss"}, priority=5, block=True)


@boss_attack_cmd.handle()
async def handle_boss_attack(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(boss_attack_cmd, event)

    result = boss_svc.attack_boss(group_id, event.user_id)
    await reply_finish(boss_attack_cmd, event, result["text"])


@boss_status_cmd.handle()
async def handle_boss_status(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(boss_status_cmd, event)

    await reply_finish(boss_status_cmd, event, boss_svc.format_boss_status(group_id))

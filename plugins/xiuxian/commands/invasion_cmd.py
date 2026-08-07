"""域外天魔入侵指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..services import invasion as invasion_svc
from .helpers import require_game, xiuxian_command, reply_finish

# 迎击天魔
invasion_attack_cmd = xiuxian_command("迎击天魔", aliases={"迎战天魔", "打天魔", "抵御天魔"}, priority=5, block=True)
# 查看入侵状态
invasion_status_cmd = xiuxian_command("天魔状态", aliases={"入侵状态", "天魔入侵"}, priority=5, block=True)


@invasion_attack_cmd.handle()
async def handle_invasion_attack(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(invasion_attack_cmd, event)
    result = invasion_svc.attack_demon(group_id, event.user_id)
    await reply_finish(invasion_attack_cmd, event, result["text"])


@invasion_status_cmd.handle()
async def handle_invasion_status(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(invasion_status_cmd, event)
    await reply_finish(invasion_status_cmd, event, invasion_svc.format_status(group_id))

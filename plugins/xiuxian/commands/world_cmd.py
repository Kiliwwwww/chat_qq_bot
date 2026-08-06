"""世界状态指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..services import world as world_svc
from .helpers import require_game, xiuxian_command, reply_finish

world_cmd = xiuxian_command("世界", aliases={"世界状态"}, priority=5, block=True)


@world_cmd.handle()
async def handle_world(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(world_cmd, event)

    world_svc.ensure_world(group_id)
    await reply_finish(world_cmd, event, world_svc.format_world_status(group_id))

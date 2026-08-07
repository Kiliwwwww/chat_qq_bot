"""种植指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..services import plant as plant_svc
from .helpers import require_game, xiuxian_command, reply_finish

plant_cmd = xiuxian_command("种植", priority=5, block=True)
harvest_cmd = xiuxian_command("收获", priority=5, block=True)
field_cmd = xiuxian_command("灵田", aliases={"我的灵田"}, priority=5, block=True)


@plant_cmd.handle()
async def handle_plant(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(plant_cmd, event)

    name = args.extract_plain_text().strip()
    if not name:
        await reply_finish(plant_cmd, event, "请指定要种植的作物，如：种植 灵草\n可种植：灵草(10分钟)/龙涎草(30分钟)/千年灵参(60分钟)")

    result = plant_svc.plant(group_id, event.user_id, name)
    await reply_finish(plant_cmd, event, result["text"])


@harvest_cmd.handle()
async def handle_harvest(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(harvest_cmd, event)

    result = plant_svc.harvest(group_id, event.user_id)
    await reply_finish(harvest_cmd, event, result["text"])


@field_cmd.handle()
async def handle_field(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(field_cmd, event)

    await reply_finish(field_cmd, event, plant_svc.format_field(group_id, event.user_id))

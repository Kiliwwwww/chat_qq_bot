"""灵宠指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..services import pet as pet_svc
from .helpers import require_game, xiuxian_command, reply_finish

pet_cmd = xiuxian_command("灵宠", aliases={"我的灵宠"}, priority=5, block=True)
feed_cmd = xiuxian_command("喂养", priority=5, block=True)


@pet_cmd.handle()
async def handle_pet(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(pet_cmd, event)
    await reply_finish(pet_cmd, event, pet_svc.format_pets(group_id, event.user_id))


@feed_cmd.handle()
async def handle_feed(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(feed_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await reply_finish(feed_cmd, event, "请指定灵宠编号，如：喂养 1（发送「灵宠」查看编号）")
    result = pet_svc.feed_pet(group_id, event.user_id, int(arg))
    await reply_finish(feed_cmd, event, result["text"])

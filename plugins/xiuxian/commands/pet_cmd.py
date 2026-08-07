"""灵宠指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..services import pet as pet_svc
from .helpers import require_game, xiuxian_command, reply_finish

pet_cmd = xiuxian_command("灵宠", aliases={"我的灵宠"}, priority=5, block=True)
feed_cmd = xiuxian_command("喂养", priority=5, block=True)
pet_shop_cmd = xiuxian_command("灵兽阁", aliases={"妖兽阁", "灵宠阁"}, priority=5, block=True)
pet_shop_buy_cmd = xiuxian_command("灵兽阁购买", aliases={"购买灵兽"}, priority=5, block=True)


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


@pet_shop_cmd.handle()
async def handle_pet_shop(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(pet_shop_cmd, event)
    await reply_finish(pet_shop_cmd, event, pet_svc.format_pet_shop())


@pet_shop_buy_cmd.handle()
async def handle_pet_shop_buy(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(pet_shop_buy_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg:
        await reply_finish(pet_shop_buy_cmd, event, "请指定灵兽编号或名称，如：灵兽阁购买 1（或 灵兽阁购买 神兽）")
    if arg.isdigit():
        index = int(arg)
    else:
        index = next((i for i, p in enumerate(constants.PET_SHOP, start=1) if arg in (p["name"], p["pet_type"])), 0)
        if not index:
            names = "、".join(p["name"] for p in constants.PET_SHOP)
            await reply_finish(pet_shop_buy_cmd, event, f"灵兽阁没有「{arg}」这只灵兽（可购：{names}）")
    result = pet_svc.buy_pet(group_id, event.user_id, index)
    await reply_finish(pet_shop_buy_cmd, event, result["text"])

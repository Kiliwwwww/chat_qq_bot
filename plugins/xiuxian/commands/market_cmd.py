"""坊市指令。"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..services import market as market_svc
from .helpers import require_game

market_cmd = on_command("坊市", aliases={"市场"}, priority=5, block=True)
market_sell_cmd = on_command("坊市出售", aliases={"出售"}, priority=5, block=True)
market_buy_cmd = on_command("坊市购买", priority=5, block=True)
market_buy_merchant_cmd = on_command("坊市购商", aliases={"购商"}, priority=5, block=True)
market_cancel_cmd = on_command("坊市撤销", aliases={"撤销挂单"}, priority=5, block=True)


@market_cmd.handle()
async def handle_market(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_cmd, event)
    await market_cmd.finish(market_svc.format_market(group_id, event.user_id))


@market_sell_cmd.handle()
async def handle_market_sell(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_sell_cmd, event)

    parts = args.extract_plain_text().strip().split()
    if len(parts) < 3:
        await market_sell_cmd.finish("格式错误！正确格式：坊市出售 <物品名> <数量> <单价>")

    from .. import constants
    from ..state import db
    item_name = parts[0]
    item_id = ""
    for key, item in constants.ITEMS.items():
        if item["name"] == item_name:
            item_id = key
            break
    if not item_id:
        # 尝试按装备展示名匹配（如：神兵·仙器）
        for inv in db.get_inventory(group_id, event.user_id):
            iid = inv["item_id"]
            if not iid.startswith("equip:"):
                continue
            p = iid.split(":")
            if len(p) == 3:
                kind = constants.EQUIPMENT_KINDS.get(p[1], {})
                if f"{kind.get('name', p[1])}·{p[2]}" == item_name:
                    item_id = iid
                    break
    if not item_id:
        await market_sell_cmd.finish(f"无法识别物品「{item_name}」，请使用背包中的物品名")

    try:
        quantity = int(parts[1])
        price = int(parts[2])
    except ValueError:
        await market_sell_cmd.finish("数量与单价必须是数字")

    result = market_svc.sell_item(group_id, event.user_id, item_id, quantity, price)
    await market_sell_cmd.finish(result["text"])


@market_buy_cmd.handle()
async def handle_market_buy(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_buy_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await market_buy_cmd.finish("请指定挂单号，如：坊市购买 3")
    result = market_svc.buy_order(group_id, event.user_id, int(arg))
    await market_buy_cmd.finish(result["text"])


@market_buy_merchant_cmd.handle()
async def handle_market_buy_merchant(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_buy_merchant_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await market_buy_merchant_cmd.finish("请指定商品编号，如：坊市购商 1")
    result = await market_svc.buy_merchant_item(group_id, event.user_id, int(arg))
    await market_buy_merchant_cmd.finish(result["text"])


@market_cancel_cmd.handle()
async def handle_market_cancel(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_cancel_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await market_cancel_cmd.finish("请指定挂单号，如：坊市撤销 3")
    result = market_svc.cancel_order(group_id, event.user_id, int(arg))
    await market_cancel_cmd.finish(result["text"])

"""坊市指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..services import market as market_svc
from ..state import db
from .helpers import require_game, xiuxian_command, reply_finish

market_cmd = xiuxian_command("坊市", aliases={"市场"}, priority=5, block=True)
market_sell_cmd = xiuxian_command("坊市出售", aliases={"出售"}, priority=5, block=True)
market_buy_cmd = xiuxian_command("坊市购买", priority=5, block=True)
market_buy_merchant_cmd = xiuxian_command("坊市购商", aliases={"购商"}, priority=5, block=True)
market_buy_breakthrough_cmd = xiuxian_command("坊市购突破", aliases={"购突破"}, priority=5, block=True)
market_cancel_cmd = xiuxian_command("坊市撤销", aliases={"撤销挂单"}, priority=5, block=True)


@market_cmd.handle()
async def handle_market(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_cmd, event)
    await reply_finish(market_cmd, event, market_svc.format_market(group_id, event.user_id))


@market_sell_cmd.handle()
async def handle_market_sell(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_sell_cmd, event)

    parts = args.extract_plain_text().strip().split()
    if len(parts) < 3:
        await reply_finish(market_sell_cmd, event, "格式错误！正确格式：坊市出售 <物品名> <数量> <单价>")

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
        await reply_finish(market_sell_cmd, event, f"无法识别物品「{item_name}」，请使用背包中的物品名")

    try:
        quantity = int(parts[1])
        price = int(parts[2])
    except ValueError:
        await reply_finish(market_sell_cmd, event, "数量与单价必须是数字")

    result = market_svc.sell_item(group_id, event.user_id, item_id, quantity, price)
    await reply_finish(market_sell_cmd, event, result["text"])


@market_buy_cmd.handle()
async def handle_market_buy(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_buy_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg:
        await reply_finish(market_buy_cmd, event, "请指定挂单号或物品名，如：坊市购买 3（或 坊市购买 灵草）")
    if arg.isdigit():
        result = market_svc.buy_order(group_id, event.user_id, int(arg))
    else:
        item_id = ""
        for key, item in constants.ITEMS.items():
            if item["name"] == arg:
                item_id = key
                break
        if not item_id:
            await reply_finish(market_buy_cmd, event, f"坊市没有「{arg}」这个物品的挂单")
        order = next((o for o in db.get_active_orders(group_id) if o["item_id"] == item_id), None)
        if not order:
            await reply_finish(market_buy_cmd, event, f"坊市没有「{arg}」的挂单")
        result = market_svc.buy_order(group_id, event.user_id, order["id"])
    await reply_finish(market_buy_cmd, event, result["text"])


@market_buy_merchant_cmd.handle()
async def handle_market_buy_merchant(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_buy_merchant_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg:
        await reply_finish(market_buy_merchant_cmd, event, "请指定商品编号或物品名，如：坊市购商 1（或 坊市购商 修炼丹）")
    goods = market_svc.get_merchant_goods(group_id)
    if arg.isdigit():
        index = int(arg)
    else:
        index = next(
            (i for i, g in enumerate(goods, start=1)
             if constants.ITEMS.get(g["item_id"], {}).get("name") == arg),
            0,
        )
        if not index:
            names = "、".join(constants.ITEMS.get(g["item_id"], {}).get("name", g["item_id"]) for g in goods)
            await reply_finish(market_buy_merchant_cmd, event, f"神秘商人没有「{arg}」这件商品（当前：{names}）")
    result = await market_svc.buy_merchant_item(group_id, event.user_id, index)
    await reply_finish(market_buy_merchant_cmd, event, result["text"])


@market_buy_breakthrough_cmd.handle()
async def handle_market_buy_breakthrough(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_buy_breakthrough_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg:
        await reply_finish(market_buy_breakthrough_cmd, event, "请指定商品编号或物品名，如：坊市购突破 1（或 坊市购突破 聚气草）")
    goods = constants.BREAKTHROUGH_MERCHANT_GOODS
    if arg.isdigit():
        index = int(arg)
    else:
        index = next(
            (i for i, g in enumerate(goods, start=1)
             if constants.ITEMS.get(g["item_id"], {}).get("name") == arg),
            0,
        )
        if not index:
            await reply_finish(market_buy_breakthrough_cmd, event, f"突破商人没有「{arg}」这件商品")
    result = await market_svc.buy_breakthrough_merchant_item(group_id, event.user_id, index)
    await reply_finish(market_buy_breakthrough_cmd, event, result["text"])


@market_cancel_cmd.handle()
async def handle_market_cancel(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(market_cancel_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await reply_finish(market_cancel_cmd, event, "请指定挂单号，如：坊市撤销 3")
    result = market_svc.cancel_order(group_id, event.user_id, int(arg))
    await reply_finish(market_cancel_cmd, event, result["text"])

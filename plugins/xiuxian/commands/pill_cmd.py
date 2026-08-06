"""服用丹药与常驻商城指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..state import db
from ..services import market as market_svc
from ..services import pill as pill_svc
from .helpers import require_game, xiuxian_command

# 服用丹药
use_pill_cmd = xiuxian_command("服用", aliases={"服丹", "使用丹药"}, priority=5, block=True)
# 常驻商城
shop_cmd = xiuxian_command("商城", aliases={"商店", "丹药商城"}, priority=5, block=True)
# 商城购买
shop_buy_cmd = xiuxian_command("商城购买", aliases={"购丹"}, priority=5, block=True)
# 商城出售
shop_sell_cmd = xiuxian_command("商城出售", aliases={"卖货", "出售道具"}, priority=5, block=True)


def _resolve_pill_key(name: str) -> str:
    for key, item in constants.ITEMS.items():
        if item.get("type") == "pill" and item["name"] == name:
            return key
    return ""


def _resolve_sell_item(group_id: int, user_id: int, name: str) -> str:
    """解析可出售物品：先匹配材料/丹药，再匹配背包中的装备"""
    for key, item in constants.ITEMS.items():
        if item["name"] == name and market_svc.get_item_buyback_price(key) > 0:
            return key
    # 装备：按展示名匹配（如：神兵·仙器）
    for inv in db.get_inventory(group_id, user_id):
        item_id = inv["item_id"]
        if not item_id.startswith("equip:"):
            continue
        parts = item_id.split(":")
        if len(parts) == 3:
            kind = constants.EQUIPMENT_KINDS.get(parts[1], {})
            if f"{kind.get('name', parts[1])}·{parts[2]}" == name:
                return item_id
    return ""


@use_pill_cmd.handle()
async def handle_use_pill(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(use_pill_cmd, event)

    name = args.extract_plain_text().strip()
    if not name:
        pills = "、".join(
            v["name"] for v in constants.ITEMS.values() if v.get("type") == "pill"
        )
        await use_pill_cmd.finish(f"请指定要服用的丹药名，如：服用 修炼丹\n可用丹药：{pills}")

    pill_key = _resolve_pill_key(name)
    if not pill_key:
        await use_pill_cmd.finish(f"没有叫「{name}」的丹药")

    result = pill_svc.use_pill(group_id, event.user_id, pill_key)
    await use_pill_cmd.finish(result["text"])


@shop_cmd.handle()
async def handle_shop(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(shop_cmd, event)
    await shop_cmd.finish(market_svc.format_shop())


@shop_buy_cmd.handle()
async def handle_shop_buy(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(shop_buy_cmd, event)

    arg = args.extract_plain_text().strip()
    if not arg.isdigit():
        await shop_buy_cmd.finish("请指定商品编号，如：商城购买 1（发送「商城」查看）")
    result = market_svc.buy_shop_item(group_id, event.user_id, int(arg))
    await shop_buy_cmd.finish(result["text"])


@shop_sell_cmd.handle()
async def handle_shop_sell(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(shop_sell_cmd, event)

    parts = args.extract_plain_text().strip().split()
    if not parts:
        await shop_sell_cmd.finish("请指定要出售的物品，如：商城出售 灵草 5\n支持出售：灵草/妖丹/灵泉/各种丹药/装备")
    name = parts[0]
    try:
        quantity = int(parts[1]) if len(parts) > 1 else 1
    except ValueError:
        await shop_sell_cmd.finish("数量必须是数字")

    item_id = _resolve_sell_item(group_id, event.user_id, name)
    if not item_id:
        await shop_sell_cmd.finish(f"无法识别可出售的物品「{name}」，请使用背包中的物品名")

    result = market_svc.sell_to_shop(group_id, event.user_id, item_id, quantity)
    await shop_sell_cmd.finish(result["text"])

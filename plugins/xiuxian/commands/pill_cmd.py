"""服用丹药与常驻商城指令。"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..services import market as market_svc
from ..services import pill as pill_svc
from .helpers import require_game

# 服用丹药
use_pill_cmd = on_command("服用", aliases={"服丹", "使用丹药"}, priority=5, block=True)
# 常驻商城
shop_cmd = on_command("商城", aliases={"商店", "丹药商城"}, priority=5, block=True)
# 商城购买
shop_buy_cmd = on_command("商城购买", aliases={"购丹"}, priority=5, block=True)


def _resolve_pill_key(name: str) -> str:
    for key, item in constants.ITEMS.items():
        if item.get("type") == "pill" and item["name"] == name:
            return key
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

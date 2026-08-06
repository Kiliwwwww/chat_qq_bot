"""炼丹、炼器、背包与装备指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..services import alchemy as alch_svc
from ..services import inventory as inv_svc
from .helpers import require_game, xiuxian_command, reply_finish

lian_dan_cmd = xiuxian_command("炼丹", priority=5, block=True)
lian_qi_cmd = xiuxian_command("炼器", priority=5, block=True)
inventory_cmd = xiuxian_command("背包", aliases={"我的背包"}, priority=5, block=True)
equip_cmd = xiuxian_command("装备", priority=5, block=True)
unequip_cmd = xiuxian_command("卸下", aliases={"卸装备"}, priority=5, block=True)


def _resolve_pill_key(name: str) -> str:
    for key, item in constants.ITEMS.items():
        if item.get("type") == "pill" and item["name"] == name:
            return key
    return ""


@lian_dan_cmd.handle()
async def handle_lian_dan(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(lian_dan_cmd, event)

    name = args.extract_plain_text().strip()
    if not name:
        recipes = [
            f"  {constants.ITEMS[k]['name']}：{'、'.join(constants.ITEMS[m]['name'] + f'×{n}' for m, n in r['materials'].items())}（{r['cost']}灵石）"
            for k, r in constants.ALCHEMY_RECIPES.items()
        ]
        await reply_finish(lian_dan_cmd, event, "⚗️ 【炼丹配方】\n" + "\n".join(recipes) + "\n💡 使用：炼丹 <丹药名>")

    pill_key = _resolve_pill_key(name)
    if not pill_key:
        await reply_finish(lian_dan_cmd, event, f"没有叫「{name}」的丹药")
    result = alch_svc.alchemy(group_id, event.user_id, pill_key)
    await reply_finish(lian_dan_cmd, event, result["text"])


@lian_qi_cmd.handle()
async def handle_lian_qi(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(lian_qi_cmd, event)
    result = alch_svc.forge(group_id, event.user_id)
    await reply_finish(lian_qi_cmd, event, result["text"])


@inventory_cmd.handle()
async def handle_inventory(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(inventory_cmd, event)
    await reply_finish(inventory_cmd, event, inv_svc.format_inventory(group_id, event.user_id))


@equip_cmd.handle()
async def handle_equip(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(equip_cmd, event)

    name = args.extract_plain_text().strip()
    if not name:
        await reply_finish(equip_cmd, event, "请指定要装备的物品名，如：装备 神兵·仙器")
    result = inv_svc.equip_item(group_id, event.user_id, name)
    await reply_finish(equip_cmd, event, result["text"])


@unequip_cmd.handle()
async def handle_unequip(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(unequip_cmd, event)

    slot = args.extract_plain_text().strip()
    slot_map = {"武器": "weapon", "法袍": "armor", "法宝": "treasure"}
    if slot in slot_map:
        slot = slot_map[slot]
    result = inv_svc.unequip_item(group_id, event.user_id, slot)
    await reply_finish(unequip_cmd, event, result["text"])

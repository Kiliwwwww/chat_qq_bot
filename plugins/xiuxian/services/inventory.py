"""背包与装备系统。"""

from .. import constants
from ..state import db


def _item_display(item_id: str, quantity: int) -> str:
    """物品展示名"""
    if item_id.startswith("equip:"):
        parts = item_id.split(":")
        if len(parts) == 3:
            kind = constants.EQUIPMENT_KINDS.get(parts[1], {})
            return f"{kind.get('name', parts[1])}·{parts[2]} ×{quantity}"
    item = constants.ITEMS.get(item_id, {})
    return f"{item.get('name', item_id)} ×{quantity}"


def format_inventory(group_id: int, user_id: int) -> str:
    """格式化背包"""
    items = db.get_inventory(group_id, user_id)
    if not items:
        return "🎒 背包空空如也，去「探索」或「炼丹」获取物品吧"

    lines = ["🎒 【我的背包】"]
    for item in items:
        lines.append(f"  {_item_display(item['item_id'], item['quantity'])}")
    lines.append("💡 使用「装备 <物品名>」可装备武器/法袍/法宝")
    return "\n".join(lines)


def _find_equip_item(group_id: int, user_id: int, name: str) -> tuple[str, int]:
    """根据名称在背包中查找装备，返回 (item_id, quantity) 或 ("", 0)"""
    for item in db.get_inventory(group_id, user_id):
        item_id = item["item_id"]
        if not item_id.startswith("equip:"):
            continue
        parts = item_id.split(":")
        if len(parts) != 3:
            continue
        kind = constants.EQUIPMENT_KINDS.get(parts[1], {})
        display = f"{kind.get('name', parts[1])}·{parts[2]}"
        if name in (display, f"{parts[1]}:{parts[2]}", parts[2]):
            return item_id, item["quantity"]
    return "", 0


def equip_item(group_id: int, user_id: int, name: str) -> dict:
    """装备物品"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    item_id, quantity = _find_equip_item(group_id, user_id, name)
    if not item_id or quantity <= 0:
        return {"ok": False, "text": f"背包中没有名为「{name}」的装备"}

    parts = item_id.split(":")
    slot = parts[1]
    quality = parts[2]

    # 卸下旧装备
    old_item = player.get(slot, "")
    if old_item and old_item != item_id:
        db.add_item(group_id, user_id, old_item, 1)

    # 穿戴新装备（从背包移除）
    db.remove_item(group_id, user_id, item_id, 1)
    db.update_player(group_id, user_id, {slot: item_id})

    kind = constants.EQUIPMENT_KINDS.get(slot, {})
    return {"ok": True, "text": f"⚔️ 已装备【{kind.get('name', slot)}·{quality}】"}


def unequip_item(group_id: int, user_id: int, slot: str) -> dict:
    """卸下装备"""
    if slot not in constants.EQUIPMENT_KINDS:
        return {"ok": False, "text": "装备槽位不存在（weapon/armor/treasure）"}
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色"}

    old_item = player.get(slot, "")
    if not old_item:
        return {"ok": False, "text": "该槽位没有装备"}
    db.add_item(group_id, user_id, old_item, 1)
    db.update_player(group_id, user_id, {slot: ""})
    kind = constants.EQUIPMENT_KINDS.get(slot, {})
    return {"ok": True, "text": f"已卸下【{kind.get('name', slot)}】并放回背包"}

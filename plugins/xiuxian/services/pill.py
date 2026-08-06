"""丹药服用系统。

玩家可服用背包中的丹药获得修为/气运等效果。
"""

from .. import constants
from ..state import db


def use_pill(group_id: int, user_id: int, pill_key: str) -> dict:
    """服用丹药，返回结果 dict"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    item = constants.ITEMS.get(pill_key)
    if not item or item.get("type") != "pill":
        return {"ok": False, "text": "没有这种丹药"}

    effect = item.get("effect", {})
    if not effect:
        return {"ok": False, "text": f"【{item['name']}】无法直接服用"}

    # 特殊丹药引导
    if "breakthrough" in effect:
        return {"ok": False, "text": f"【{item['name']}】在「突破」时使用效果最佳（发送「突破 用破境丹」）"}
    if "pet_exp" in effect:
        return {"ok": False, "text": f"【{item['name']}】用于喂养灵宠，请发送「喂养 <编号>」使用"}

    if db.get_item_quantity(group_id, user_id, pill_key) <= 0:
        return {"ok": False, "text": f"你没有【{item['name']}】，可在「商城」购买或「炼丹」炼制"}

    db.remove_item(group_id, user_id, pill_key, 1)

    lines = [f"💊 服用【{item['name']}】成功！"]
    fortune = player.get("fortune", 1000)

    if "progress" in effect:
        gain = effect["progress"]
        # 服丹效果受灵根品质与气运加成
        quality_mult = 1 + constants.QUALITIES.get(player.get("spirit_quality", "废品"), 0.05)
        luck_mult = 1 + rng_factor(fortune) * 2
        final_gain = int(gain * quality_mult * luck_mult)

        realm_index = player.get("realm", 0)
        capacity = constants.REALMS[realm_index]["capacity"]
        current = player.get("realm_progress", 0) + final_gain
        if capacity:
            current = min(current, capacity)
        db.update_player(group_id, user_id, {"realm_progress": current})
        lines.append(f"✨ 修为 +{final_gain}！")

    if "fortune" in effect:
        gain = effect["fortune"]
        db.update_player(group_id, user_id, {"fortune": fortune + gain})
        lines.append(f"🍀 气运 +{gain}！")

    if "hp" in effect:
        new_hp = player.get("hp", 100) + effect["hp"]
        db.update_player(group_id, user_id, {"hp": new_hp})
        lines.append(f"❤️ 气血上限 +{effect['hp']}！")

    return {"ok": True, "text": "\n".join(lines)}


def rng_factor(fortune: int) -> float:
    """气运修正因子（与 services.rng.fortune_factor 保持一致）"""
    from .rng import fortune_factor
    return fortune_factor(fortune)

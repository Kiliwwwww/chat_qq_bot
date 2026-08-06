"""炼丹炼器系统。"""

from .. import constants
from ..state import db
from . import rng


def _quality_bonus(quality: str) -> float:
    """灵根品质对炼丹/炼器成功率的影响"""
    idx = constants.QUALITY_ORDER.index(quality) if quality in constants.QUALITY_ORDER else 0
    return idx * 0.02


def alchemy(group_id: int, user_id: int, pill_key: str) -> dict:
    """炼制丹药"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    if pill_key not in constants.ITEMS or constants.ITEMS[pill_key]["type"] != "pill":
        return {"ok": False, "text": "该丹药不存在"}

    if pill_key not in constants.ALCHEMY_RECIPES:
        return {"ok": False, "text": "该丹药没有配方"}

    recipe = constants.ALCHEMY_RECIPES[pill_key]

    # 检查材料
    for mat_id, qty in recipe["materials"].items():
        have = db.get_item_quantity(group_id, user_id, mat_id)
        if have < qty:
            mat_name = constants.ITEMS.get(mat_id, {}).get("name", mat_id)
            return {"ok": False, "text": f"材料不足：需要 {mat_name}×{qty}（当前 {have}）"}

    # 检查灵石
    if player.get("coin", 0) < recipe["cost"]:
        return {"ok": False, "text": f"灵石不足，炼丹需要 {recipe['cost']} 灵石"}

    # 消耗材料与灵石
    for mat_id, qty in recipe["materials"].items():
        db.remove_item(group_id, user_id, mat_id, qty)
    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - recipe["cost"]})

    # 成功率
    level = player.get("alchemy_level", 1)
    base = 0.55 + level * 0.03 + _quality_bonus(player.get("spirit_quality", ""))
    fortune = player.get("fortune", 1000)
    success = rng.luck_roll(base, fortune)

    # 炼丹经验
    exp_gain = 20
    new_exp = player.get("alchemy_exp", 0) + exp_gain
    new_level = level
    while new_level < 10 and new_exp >= new_level * 100:
        new_level += 1
    db.update_player(group_id, user_id, {"alchemy_exp": new_exp, "alchemy_level": new_level})

    pill_name = constants.ITEMS[pill_key]["name"]
    if success:
        count = 1 + (level // 3)
        db.add_item(group_id, user_id, pill_key, count)
        text = f"🔥 【炼丹成功】炼得 {pill_name}×{count}！"
        if new_level > level:
            text += f"\n🎓 炼丹等级提升至 {new_level} 级！"
        return {"ok": True, "text": text}
    else:
        text = f"💨 【炼丹失败】{pill_name}炼制失败，材料化为灰烬"
        if new_level > level:
            text += f"\n🎓 炼丹等级提升至 {new_level} 级！"
        return {"ok": True, "text": text}


def forge(group_id: int, user_id: int) -> dict:
    """炼制装备"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    # 检查材料
    for mat_id, qty in constants.FORGE_COST["materials"].items():
        have = db.get_item_quantity(group_id, user_id, mat_id)
        if have < qty:
            mat_name = constants.ITEMS.get(mat_id, {}).get("name", mat_id)
            return {"ok": False, "text": f"材料不足：需要 {mat_name}×{qty}（当前 {have}）"}

    cost = constants.FORGE_COST["cost"]
    if player.get("coin", 0) < cost:
        return {"ok": False, "text": f"灵石不足，炼器需要 {cost} 灵石"}

    for mat_id, qty in constants.FORGE_COST["materials"].items():
        db.remove_item(group_id, user_id, mat_id, qty)
    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - cost})

    level = player.get("forge_level", 1)
    base = 0.6 + level * 0.03 + _quality_bonus(player.get("spirit_quality", ""))
    fortune = player.get("fortune", 1000)
    success = rng.luck_roll(base, fortune)

    exp_gain = 25
    new_exp = player.get("forge_exp", 0) + exp_gain
    new_level = level
    while new_level < 10 and new_exp >= new_level * 120:
        new_level += 1
    db.update_player(group_id, user_id, {"forge_exp": new_exp, "forge_level": new_level})

    if not success:
        text = "⚒️ 【炼器失败】炉火熄灭，材料尽毁"
        if new_level > level:
            text += f"\n🎓 炼器等级提升至 {new_level} 级！"
        return {"ok": True, "text": text}

    # 品质受炼器等级与气运影响
    weights = {i: q["weight"] for i, q in enumerate(constants.EQUIPMENT_QUALITIES)}
    positive = [i for i in range(len(constants.EQUIPMENT_QUALITIES)) if i >= 2]
    shifted = rng.positive_shift(weights, fortune, positive)
    quality = constants.EQUIPMENT_QUALITIES[rng.weighted_choice_dict(shifted)]

    kind = rng.weighted_choice(list(constants.EQUIPMENT_KINDS.values()))
    slot = next(k for k, v in constants.EQUIPMENT_KINDS.items() if v == kind)
    item_id = f"equip:{slot}:{quality['name']}"
    db.add_item(group_id, user_id, item_id, 1)

    text = f"⚒️ 【炼器成功】获得【{kind['name']}·{quality['name']}】！"
    if new_level > level:
        text += f"\n🎓 炼器等级提升至 {new_level} 级！"
    return {"ok": True, "text": text}

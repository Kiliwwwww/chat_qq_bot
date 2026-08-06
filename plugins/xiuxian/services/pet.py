"""灵宠系统。"""

from .. import constants
from ..state import db


def _find_pet_food(group_id: int, user_id: int) -> tuple[str, int]:
    """查找背包中可用于喂养灵宠的丹药，优先消耗经验更高的（凝魄丹→精元丹）。"""
    best = ("", 0)
    for inv in db.get_inventory(group_id, user_id):
        item = constants.ITEMS.get(inv["item_id"], {})
        if item.get("type") == "pill" and "pet_exp" in item.get("effect", {}):
            exp = item["effect"]["pet_exp"]
            if exp > best[1]:
                best = (inv["item_id"], exp)
    return best


def feed_pet(group_id: int, user_id: int, pet_index: int) -> dict:
    """使用丹药喂养灵宠（精元丹/凝魄丹）"""
    pets = db.get_pets(group_id, user_id)
    if not pets:
        return {"ok": False, "text": "你还没有灵宠，去探索获取吧"}

    if pet_index < 1 or pet_index > len(pets):
        return {"ok": False, "text": "灵宠编号不存在"}

    food_id, exp_gain = _find_pet_food(group_id, user_id)
    if not food_id:
        return {"ok": False, "text": "没有喂养灵宠的丹药（精元丹/凝魄丹），可炼丹或去坊市购买"}

    pet = pets[pet_index - 1]
    db.remove_item(group_id, user_id, food_id, 1)

    new_exp = pet["exp"] + exp_gain
    level = pet["level"]
    leveled_up = False
    while new_exp >= constants.PET_EXP_BASE * level:
        new_exp -= constants.PET_EXP_BASE * level
        level += 1
        leveled_up = True

    db.update_pet(group_id, user_id, pet["pet_id"], {"exp": new_exp, "level": level})
    pet_type = constants.PET_TYPE_BY_ID.get(pet["pet_type"], {})
    text = f"🍬 喂养【{pet_type.get('name', '灵宠')}】成功，经验+{exp_gain}！"
    if leveled_up:
        text += f"\n📈 灵宠等级提升至 {level} 级！挂机收益增加！"
    return {"ok": True, "text": text}


def format_pets(group_id: int, user_id: int) -> str:
    """格式化灵宠列表"""
    pets = db.get_pets(group_id, user_id)
    if not pets:
        return "🐾 你还没有灵宠，去「探索」秘境或妖兽森林碰碰运气吧"

    lines = ["🐾 【我的灵宠】"]
    for i, pet in enumerate(pets, start=1):
        pet_type = constants.PET_TYPE_BY_ID.get(pet["pet_type"], {})
        lines.append(
            f"{i}. {pet_type.get('name', pet['pet_type'])} Lv.{pet['level']} "
            f"（exp {pet['exp']}/{constants.PET_EXP_BASE * pet['level']}）"
        )
    lines.append("💡 使用「喂养 <编号>」可消耗精元丹喂养灵宠")
    return "\n".join(lines)

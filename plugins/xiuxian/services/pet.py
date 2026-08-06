"""灵宠系统。"""

from .. import constants
from ..state import db


def feed_pet(group_id: int, user_id: int, pet_index: int) -> dict:
    """使用精元丹喂养灵宠"""
    pets = db.get_pets(group_id, user_id)
    if not pets:
        return {"ok": False, "text": "你还没有灵宠，去探索获取吧"}

    if pet_index < 1 or pet_index > len(pets):
        return {"ok": False, "text": "灵宠编号不存在"}

    if db.get_item_quantity(group_id, user_id, "jingyuan_dan") <= 0:
        return {"ok": False, "text": "没有精元丹，可炼丹或去坊市购买"}

    pet = pets[pet_index - 1]
    db.remove_item(group_id, user_id, "jingyuan_dan", 1)

    exp_gain = constants.ITEMS["jingyuan_dan"]["effect"]["pet_exp"]
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

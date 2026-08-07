"""灵宠系统。"""

import random

from .. import constants
from ..state import db


def _new_pet_id(group_id: int, user_id: int) -> int:
    """生成不与现有灵宠冲突的灵宠 id"""
    pet_id = random.randint(1, 99999999)
    retry = 0
    while db.get_pet(group_id, user_id, pet_id) and retry < 5:
        pet_id = random.randint(1, 99999999)
        retry += 1
    return pet_id


def format_pet_shop() -> str:
    """灵兽阁：可花费灵石直接购买灵兽"""
    lines = ["🐾 【灵兽阁】", "💡 可花费灵石直接购买灵兽（探索也有概率免费获得）"]
    for i, pet in enumerate(constants.PET_SHOP, start=1):
        lines.append(f"{i}. {pet['name']} - {pet['price']} 灵石")
        lines.append(f"   💬 {pet['desc']}")
    lines.append("💡 使用「灵兽阁购买 <编号>」购买")
    return "\n".join(lines)


def buy_pet(group_id: int, user_id: int, index: int) -> dict:
    """从灵兽阁购买灵兽"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    pet_shop = constants.PET_SHOP
    if index < 1 or index > len(pet_shop):
        return {"ok": False, "text": f"编号不存在（1~{len(pet_shop)}）"}

    pet = pet_shop[index - 1]
    if player.get("coin", 0) < pet["price"]:
        return {"ok": False, "text": f"灵石不足！购买【{pet['name']}】需要 {pet['price']} 灵石（当前 {player.get('coin', 0)}）"}

    pet_id = _new_pet_id(group_id, user_id)
    db.add_pet(group_id, user_id, pet_id, pet["pet_type"], pet["name"])
    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - pet["price"]})
    return {"ok": True, "text": f"🐾 你花费 {pet['price']} 灵石，购买了一只【{pet['name']}】！\n💬 {pet['desc']}\n💡 发送「灵宠」查看，用「喂养」升级"}


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
    """格式化灵宠列表（显示每只灵宠的挂机修炼加成）"""
    pets = db.get_pets(group_id, user_id)
    if not pets:
        return "🐾 你还没有灵宠，去「探索」秘境、妖兽森林或万妖山碰碰运气吧\n💡 灵宠可为你的挂机修炼提供收益加成，等级越高加成越多"

    lines = ["🐾 【我的灵宠】", "💡 灵宠作用：挂机修炼收益 +（每级加成 × 等级）%"]
    total_bonus = 0.0
    for i, pet in enumerate(pets, start=1):
        pet_type = constants.PET_TYPE_BY_ID.get(pet["pet_type"], {})
        rate = pet_type.get("rate", 0)
        level = pet.get("level", 1)
        bonus = rate * level * 100
        total_bonus += bonus
        lines.append(
            f"{i}. {pet_type.get('name', pet['pet_type'])} Lv.{level} "
            f"（exp {pet['exp']}/{constants.PET_EXP_BASE * level}）"
        )
        lines.append(
            f"   💬 {pet_type.get('desc', '')}｜当前挂机收益 +{bonus:.0f}%"
        )
    lines.append(f"📈 灵宠合计：挂机修炼收益 +{total_bonus:.0f}%")

    # 万灵圣体翻倍
    player = db.get_player(group_id, user_id)
    if player and player.get("physique") == "wanling_st":
        lines.append("✨ 万灵圣体加持：灵宠收益翻倍！")
    lines.append("💡 使用「喂养 <编号>」消耗精元丹/凝魄丹提升等级，等级越高加成越多")
    return "\n".join(lines)

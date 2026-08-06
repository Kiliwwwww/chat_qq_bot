"""探索系统。

探索不同地点获得资源/奇遇/危险，受气运影响，有冷却时间。
"""

import random
import time

from .. import constants
from ..state import config, db
from . import rng

# 各地点探索结果池
# key: 结果类型；coins/items/progress 为产出；risk 为危险结果
EXPLORE_POOL = {
    "洞府": [
        {"key": "coin", "weight": 35, "text": "在洞府密室中发现了一些前人遗留的灵石", "coins": 50},
        {"key": "lingcao", "weight": 22, "text": "在洞府后院采到几株灵草", "items": {"lingcao": 2}},
        {"key": "progress", "weight": 18, "text": "触景生情，感悟天地之道", "progress": 120},
        {"key": "lingquan", "weight": 9, "text": "发现一处隐蔽的灵泉", "items": {"lingquan": 1}},
        {"key": "xuantie", "weight": 8, "text": "在洞府矿藏中挖到一块玄铁", "items": {"xuantie": 1}},
        {"key": "shoupi", "weight": 6, "text": "找到一张结实的兽皮", "items": {"shoupi": 1}},
        {"key": "pet", "weight": 3, "text": "捡到一枚神秘的灵宠蛋"},
        {"key": "equip", "weight": 2, "text": "在角落找到一件蒙尘的宝物"},
    ],
    "灵脉": [
        {"key": "coin", "weight": 30, "text": "在灵脉中采掘到大量灵石矿", "coins": 120},
        {"key": "progress", "weight": 26, "text": "借灵脉之势参悟道法，修为大进", "progress": 300},
        {"key": "lingquan", "weight": 18, "text": "灵脉深处涌出一汪灵泉", "items": {"lingquan": 2}},
        {"key": "xuantie", "weight": 10, "text": "采到一块高品质玄铁", "items": {"xuantie": 2}},
        {"key": "xingchenshi", "weight": 5, "text": "在灵脉深处发现星辰石", "items": {"xingchenshi": 1}},
        {"key": "pet", "weight": 7, "text": "灵脉中孕育着一枚灵兽蛋"},
        {"key": "equip", "weight": 6, "text": "从矿脉中挖出一件埋藏已久的法宝"},
    ],
    "妖兽森林": [
        {"key": "yaodan", "weight": 28, "text": "猎杀妖兽，收获妖丹", "items": {"yaodan": 2}},
        {"key": "coin", "weight": 20, "text": "从妖兽巢穴搜刮到灵石", "coins": 100},
        {"key": "shoupi", "weight": 15, "text": "剥下妖兽的兽皮", "items": {"shoupi": 2}},
        {"key": "progress", "weight": 13, "text": "与妖兽搏斗，实战感悟颇多", "progress": 200},
        {"key": "xuantie", "weight": 8, "text": "从妖兽巢穴中找到玄铁", "items": {"xuantie": 1}},
        {"key": "pet", "weight": 7, "text": "捕获一只幼兽作为灵宠"},
        {"key": "equip", "weight": 5, "text": "从妖兽尸体旁捡到一件宝物"},
        {"key": "risk", "weight": 12, "text": "遭遇强大妖兽，重伤而逃", "lose_coins": 60},
    ],
    "秘境": [
        {"key": "equip", "weight": 18, "text": "在秘境宝库中发现稀世神兵"},
        {"key": "progress", "weight": 22, "text": "秘境灵气充沛，修为暴涨", "progress": 800},
        {"key": "yaodan", "weight": 12, "text": "猎杀秘境守卫妖兽，获得妖丹", "items": {"yaodan": 3}},
        {"key": "lingquan", "weight": 9, "text": "饮下秘境灵泉，脱胎换骨", "items": {"lingquan": 3}},
        {"key": "longxiancao", "weight": 8, "text": "采到一株龙涎草", "items": {"longxiancao": 1}},
        {"key": "qiannian_ls", "weight": 6, "text": "寻得千年灵参", "items": {"qiannian_ls": 1}},
        {"key": "xingchenshi", "weight": 7, "text": "拾得一枚星辰石", "items": {"xingchenshi": 2}},
        {"key": "zijinsha", "weight": 8, "text": "找到一把紫金砂", "items": {"zijinsha": 1}},
        {"key": "pet", "weight": 9, "text": "秘境中收服一只上古异兽"},
        {"key": "coin", "weight": 8, "text": "秘境中藏有大量灵石", "coins": 300},
        {"key": "risk", "weight": 10, "text": "触发秘境机关，狼狈逃离", "lose_coins": 100},
    ],
}

# 气运修正的正面结果
_POSITIVE_KEYS = [
    "coin", "lingcao", "yaodan", "lingquan", "progress",
    "pet", "equip", "xuantie", "zijinsha", "shoupi",
    "longxiancao", "xingchenshi", "qiannian_ls",
]

# 各地点探索的基础灵石收益（每次探索必定获得）
_LOCATION_BASE_COINS = {
    "洞府": 30,
    "灵脉": 60,
    "妖兽森林": 80,
    "秘境": 150,
}


def _grant_pet(group_id: int, user_id: int) -> str:
    """随机获得一只灵宠，返回宠物描述"""
    pet_type = rng.weighted_choice(constants.PET_TYPES)
    pet_id = random.randint(1, 99999999)
    retry = 0
    while db.get_pet(group_id, user_id, pet_id) and retry < 5:
        pet_id = random.randint(1, 99999999)
        retry += 1
    db.add_pet(group_id, user_id, pet_id, pet_type["id"], pet_type["name"])
    return f"获得灵宠【{pet_type['name']}】（{pet_type['desc']}）"


def _grant_equip(group_id: int, user_id: int) -> str:
    """随机获得一件装备，返回装备描述"""
    quality = rng.weighted_choice(constants.EQUIPMENT_QUALITIES)
    kind = random.choice(list(constants.EQUIPMENT_KINDS.values()))
    item_id = f"equip:{next(k for k, v in constants.EQUIPMENT_KINDS.items() if v == kind)}:{quality['name']}"
    db.add_item(group_id, user_id, item_id, 1)
    return f"获得【{kind['name']}·{quality['name']}】"


def explore(group_id: int, user_id: int, location: str) -> dict:
    """执行一次探索，返回结果 dict"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    from . import combat
    combat.try_revive(group_id, user_id)
    player = db.get_player(group_id, user_id)
    if combat.is_dead(player):
        return {"ok": False, "text": f"你已归西，气血归零无法探索！还需 {combat.dead_remain_seconds(player)} 秒复活"}
    if combat.get_cur_hp(player) <= 0:
        return {"ok": False, "text": "你气血耗尽，无法探索！服用回灵丹/大还丹恢复气血"}

    if db.get_cultivation(group_id, user_id):
        return {"ok": False, "text": "你正在闭关修炼中，无法探索，先「出关」吧"}

    if location not in constants.LOCATIONS:
        return {"ok": False, "text": f"未知探索地点，可选：{'、'.join(constants.LOCATIONS.keys())}"}

    if location == "秘境" and not _secret_realm_open_check(group_id):
        return {"ok": False, "text": "秘境尚未开启，等待「上古秘境」事件出现吧"}

    # 冷却检查
    cooldown_until = db.get_explore_cooldown(group_id, user_id)
    if time.time() < cooldown_until:
        remain = int(cooldown_until - time.time())
        return {"ok": False, "text": f"探索消耗心神，还需 {remain} 秒才能再次探索"}

    # 加权抽取结果（气运向正面倾斜）
    pool = EXPLORE_POOL[location]
    weights = {i: p["weight"] for i, p in enumerate(pool)}
    positive = [i for i, p in enumerate(pool) if p["key"] in _POSITIVE_KEYS]
    shifted = rng.positive_shift(weights, player.get("fortune", 1000), positive)
    result_index = rng.weighted_choice_dict(shifted)
    outcome = pool[result_index]

    # 设置冷却
    db.set_explore_cooldown(group_id, user_id, time.time() + config.explore_cooldown)

    result = {"ok": True, "text": f"🗺️ 【探索·{location}】\n{outcome['text']}", "gains": []}

    # 应用产出
    fortune = player.get("fortune", 1000)

    # 基础灵石收益（每次探索必定获得）
    base_coins = _LOCATION_BASE_COINS.get(location, 0)
    if base_coins > 0:
        db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + base_coins})
        result["gains"].append(f"+{base_coins} 灵石")

    if outcome.get("coins"):
        db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + outcome["coins"]})
        result["gains"].append(f"+{outcome['coins']} 灵石")
    if outcome.get("lose_coins"):
        lost = min(outcome["lose_coins"], player.get("coin", 0))
        db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - lost})
        result["gains"].append(f"-{lost} 灵石")

    if outcome.get("progress"):
        realm_index = player.get("realm", 0)
        capacity = constants.REALMS[realm_index]["capacity"]
        new_progress = player.get("realm_progress", 0) + outcome["progress"]
        if capacity:
            new_progress = min(new_progress, capacity)
        db.update_player(group_id, user_id, {"realm_progress": new_progress})
        result["gains"].append(f"+{outcome['progress']} 修为")

    if outcome.get("items"):
        for item_id, qty in outcome["items"].items():
            db.add_item(group_id, user_id, item_id, qty)
            item_name = constants.ITEMS.get(item_id, {}).get("name", item_id)
            result["gains"].append(f"+{qty} {item_name}")

    if outcome["key"] == "pet":
        pet_text = _grant_pet(group_id, user_id)
        result["text"] += f"\n🐾 {pet_text}"
    if outcome["key"] == "equip":
        equip_text = _grant_equip(group_id, user_id)
        result["text"] += f"\n🎁 {equip_text}"

    # 危险结果扣除血量（血量过低需回血，归西则 60 秒后复活）
    if outcome["key"] == "risk":
        dmg = combat.apply_negative_damage(group_id, user_id)
        result["text"] += f"\n🩸 {dmg['text']}"

    # 高气运额外触发隐藏机缘（仙缘降临事件提升触发率与奖励）
    from . import world
    luck_mult = world.explore_luck_multiplier(group_id)
    if rng.luck_roll(0.15 * luck_mult, fortune):
        bonus_coins = random.randint(30, 120) * luck_mult
        db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + int(bonus_coins)})
        result["text"] += f"\n🌟 天道垂青！额外获得 {int(bonus_coins)} 灵石"

    return result


def _secret_realm_open_check(group_id: int) -> bool:
    from . import world
    return world.is_secret_realm_open(group_id)

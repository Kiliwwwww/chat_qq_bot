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
        {"key": "zijinsha", "weight": 5, "text": "在妖兽巢穴中挖到紫金砂", "items": {"zijinsha": 1}},
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
    "灵药谷": [
        {"key": "lingcao", "weight": 28, "text": "采到一大片灵草", "items": {"lingcao": 3}},
        {"key": "lingquan", "weight": 22, "text": "发现灵药谷深处的一汪灵泉", "items": {"lingquan": 2}},
        {"key": "longxiancao", "weight": 15, "text": "寻得一株龙涎草", "items": {"longxiancao": 1}},
        {"key": "qiannian_ls", "weight": 10, "text": "采到一株千年灵参", "items": {"qiannian_ls": 1}},
        {"key": "progress", "weight": 10, "text": "药香扑鼻，闻之修为精进", "progress": 300},
        {"key": "coin", "weight": 7, "text": "捡到采药人遗留的灵石", "coins": 120},
        {"key": "risk", "weight": 8, "text": "惊动守药灵兽，被追咬逃窜", "lose_coins": 60},
    ],
    "万妖山": [
        {"key": "yaodan", "weight": 28, "text": "猎杀群妖，收获大量妖丹", "items": {"yaodan": 3}},
        {"key": "shoupi", "weight": 18, "text": "剥下妖王的皮毛", "items": {"shoupi": 2}},
        {"key": "coin", "weight": 14, "text": "洗劫妖巢，搜出灵石", "coins": 150},
        {"key": "pet", "weight": 10, "text": "收服一只万妖山灵兽"},
        {"key": "progress", "weight": 10, "text": "与妖兽厮杀，实战大进", "progress": 250},
        {"key": "equip", "weight": 6, "text": "从妖将尸骸上捡到宝物"},
        {"key": "zijinsha", "weight": 8, "text": "在妖王巢穴深处挖到紫金砂", "items": {"zijinsha": 1}},
        {"key": "risk", "weight": 16, "text": "遭遇妖王，重伤而逃", "lose_coins": 100},
    ],
    "星辰殿": [
        {"key": "progress", "weight": 28, "text": "观星悟道，参悟星辰之力", "progress": 500},
        {"key": "xingchenshi", "weight": 18, "text": "拾得坠落的星辰石", "items": {"xingchenshi": 1}},
        {"key": "coin", "weight": 15, "text": "在星辉下捡到灵石", "coins": 180},
        {"key": "equip", "weight": 14, "text": "星辰殿角落有件星辉法宝"},
        {"key": "pet", "weight": 10, "text": "星灵化形，认你为主"},
        {"key": "risk", "weight": 15, "text": "被星辰阵法反噬", "lose_coins": 100},
    ],
    "远古战场": [
        {"key": "equip", "weight": 24, "text": "在尸骸堆中寻得上古神兵"},
        {"key": "coin", "weight": 20, "text": "从战死修士遗骸搜到灵石", "coins": 200},
        {"key": "xuantie", "weight": 14, "text": "挖到一块上古玄铁", "items": {"xuantie": 2}},
        {"key": "progress", "weight": 14, "text": "感悟战场杀伐之意，修为暴涨", "progress": 400},
        {"key": "pet", "weight": 5, "text": "战场残魂化作灵宠追随"},
        {"key": "risk", "weight": 23, "text": "触发上古战魂，被群攻而逃", "lose_coins": 120},
    ],
    "幽冥深渊": [
        {"key": "equip", "weight": 20, "text": "深渊宝库中取出一件至宝"},
        {"key": "progress", "weight": 20, "text": "在死气中淬炼心神，修为暴涨", "progress": 700},
        {"key": "xingchenshi", "weight": 15, "text": "采到深渊之底的星辰石", "items": {"xingchenshi": 2}},
        {"key": "longxiancao", "weight": 10, "text": "寻得深渊幽冥草与灵参", "items": {"longxiancao": 1, "qiannian_ls": 1}},
        {"key": "coin", "weight": 10, "text": "搜刮深渊遗宝灵石", "coins": 250},
        {"key": "pet", "weight": 5, "text": "收服深渊幽兽"},
        {"key": "risk", "weight": 20, "text": "被深渊魔物围攻，狼狈逃出", "lose_coins": 150},
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
    "灵药谷": 40,
    "万妖山": 90,
    "星辰殿": 100,
    "远古战场": 120,
    "幽冥深渊": 160,
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

    from . import world
    if not world.is_location_open(group_id, location):
        event_name = world.location_open_event(location)
        if event_name:
            return {"ok": False, "text": f"{location}尚未开启，等待「{event_name}」事件出现吧"}
        return {"ok": False, "text": f"{location}尚未开启"}

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
    from . import debuff
    fortune = debuff.effective_fortune(player)

    # 负面状态掉血（如丹药中毒）
    tick = debuff.damage_per_hour(player)
    if tick > 0:
        dmg = combat.take_damage(group_id, user_id, int(tick))
        result["text"] += f"\n🩸 体内淤毒发作，损失 {int(tick)} 点气血！"

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

    # 随机奇遇（仙缘降临事件大幅提升触发率）
    if rng.luck_roll(constants.ENCOUNTER_CHANCE * luck_mult, fortune):
        result["text"] += _apply_encounter(group_id, user_id, fortune, luck_mult)

    return result


def _apply_encounter(group_id: int, user_id: int, fortune: int, luck_mult: float) -> str:
    """随机触发一次探索奇遇，返回追加文本。"""
    from . import combat, cultivation as cult

    player = db.get_player(group_id, user_id)
    enc = rng.weighted_choice(constants.ENCOUNTERS)
    text = f"\n\n🎇 【奇遇·{enc['name']}】{enc['desc']}"

    if rng.luck_roll(enc["success_chance"], fortune):
        succ = enc["success"]
        gains = []
        # 材料/丹药
        for iid, qty in succ.get("items", {}).items():
            db.add_item(group_id, user_id, iid, qty)
            gains.append(f"{constants.ITEMS.get(iid, {}).get('name', iid)}×{qty}")
        # 修为
        if succ.get("progress"):
            realm_index = player.get("realm", 0)
            capacity = constants.REALMS[realm_index]["capacity"]
            current = player.get("realm_progress", 0) + succ["progress"]
            if capacity:
                current = min(current, capacity)
            db.update_player(group_id, user_id, {"realm_progress": current})
            gains.append(f"修为 +{succ['progress']}")
        # 灵石
        if succ.get("coins"):
            db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + succ["coins"]})
            gains.append(f"灵石 +{succ['coins']}")
        # 灵宠
        if succ.get("pet"):
            gains.append(_grant_pet(group_id, user_id))
        # 装备
        if succ.get("equip"):
            gains.append(_grant_equip(group_id, user_id))
        # 功法熟练度
        if succ.get("gongfa_exp"):
            for g in db.get_gongfas(group_id, user_id):
                cult.add_gongfa_exp(group_id, user_id, g["gongfa_id"], succ["gongfa_exp"])
            gains.append(f"功法熟练度 +{succ['gongfa_exp']}")

        text += f"\n✨ {succ['text']}"
        if gains:
            text += "\n🎁 " + "、".join(gains)
        return text

    # 失败惩罚
    fail = enc["fail"]
    if fail.get("damage"):
        dmg = combat.apply_negative_damage(group_id, user_id, fail["damage"])
        text += f"\n💥 {fail['text']}"
        text += f"\n🩸 {dmg['text']}"
    else:
        text += f"\n💥 {fail['text']}"
    if fail.get("lose_coins"):
        lost = min(fail["lose_coins"], player.get("coin", 0))
        db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - lost})
        text += f"\n💸 丢失 {lost} 灵石"
    return text

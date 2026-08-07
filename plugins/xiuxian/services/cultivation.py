"""挂机修炼系统。

玩家「闭关」后离线挂机，再次「出关」时根据离线时长结算收益。
"""

import random
import time

from .. import constants
from ..state import config, db
from . import combat, debuff, rng, world


def calculate_rate(group_id: int, player: dict, location: str) -> float:
    """计算挂机修炼速率（修为/小时）"""
    quality_mult = constants.QUALITIES.get(player.get("spirit_quality", "废品"), 0.05)
    location_cfg = constants.LOCATIONS.get(location, constants.LOCATIONS["洞府"])
    location_mult = location_cfg["multiplier"]

    # 妖兽暴动事件提升妖兽森林收益
    if location == "妖兽森林":
        location_mult *= world.forest_multiplier(group_id)

    world_mult = world.cultivation_multiplier(group_id)

    # 功法修炼加成
    gongfa_bonus = 0.0
    gongfas = db.get_gongfas(group_id, player["user_id"])
    for g in gongfas:
        info = constants.GONGFA_BY_ID.get(g["gongfa_id"])
        if not info or info["attr"] != "cultivation":
            continue
        mult = constants.PROFICIENCY_MULT[g.get("level", 0)]
        bonus = info["bonus"] * mult
        # 天魔体提升魔系功法效果
        if player.get("physique") == "tianmo_ti" and info["root"] == "魔":
            bonus *= 1.5
        gongfa_bonus += bonus

    # 特殊体质修炼加成
    physique_bonus = 0.0
    phys = player.get("physique", "")
    if phys:
        p = constants.PHYSIQUE_BY_ID.get(phys)
        if p:
            physique_bonus = p.get("rate", 0.0)

    # 转世重生的永久修炼加成
    rebirth_bonus = player.get("rebirth_count", 0) * config.rebirth_rate_bonus

    # 灵宠加成（万灵圣体收益翻倍）
    pet_bonus = sum(
        constants.PET_TYPE_BY_ID.get(p["pet_type"], {}).get("rate", 0.0) * p.get("level", 1)
        for p in db.get_pets(group_id, player["user_id"])
    )
    if player.get("physique") == "wanling_st":
        pet_bonus *= 2

    # 弟子加成（紫金道体加速翻倍且上限+1；玄阴道体被收为弟子时师父受益翻倍）
    furnaces = db.get_furnaces_by_owner(group_id, player["user_id"])
    furnace_limit = config.max_furnace
    furnace_rate = constants.FURNACE_RATE_BONUS
    if player.get("physique") == "zijin_luti":
        furnace_rate = constants.FURNACE_RATE_BONUS * 2
        furnace_limit = config.max_furnace + 1
    furnace_bonus = 0.0
    for f in furnaces[:furnace_limit]:
        bonus = furnace_rate
        target = db.get_player(group_id, f["target_id"])
        if target and target.get("physique") == "xuanyin_dinglu":
            bonus *= 2
        furnace_bonus += bonus

    # 负面状态（debuff）对修炼速率的影响
    debuff_bonus = debuff.rate_bonus(player)

    rate = (
        constants.BASE_CULTIVATION_RATE
        * quality_mult
        * location_mult
        * world_mult
        * (1 + gongfa_bonus + physique_bonus + rebirth_bonus + pet_bonus + furnace_bonus + debuff_bonus)
    )
    return max(1.0, rate)


def _location_risk(group_id: int, location: str) -> float:
    """计算地点风险概率"""
    location_cfg = constants.LOCATIONS.get(location, constants.LOCATIONS["洞府"])
    risk = location_cfg["risk"]
    if location == "妖兽森林":
        risk += world.forest_risk_bonus(group_id)
    return min(0.8, risk)


def add_gongfa_exp(group_id: int, user_id: int, gongfa_id: str, exp: float) -> tuple[int, int]:
    """为功法增加熟练度经验，返回 (旧等级, 新等级)"""
    g = db.get_gongfa(group_id, user_id, gongfa_id)
    if not g:
        return 0, 0
    old_level = g["level"]
    new_exp = g["exp"] + exp
    new_level = old_level
    while new_level < len(constants.PROFICIENCY_EXP) - 1 and new_exp >= constants.PROFICIENCY_EXP[new_level + 1]:
        new_level += 1
    db.update_gongfa(group_id, user_id, gongfa_id, {"exp": new_exp, "level": new_level})
    return old_level, new_level


def start_cultivating(group_id: int, user_id: int, location: str) -> tuple[bool, str]:
    """开始闭关挂机"""
    player = db.get_player(group_id, user_id)
    if not player:
        return False, "你还没有修仙角色，发送「我要修仙」创建角色"

    inv_block = world.invasion_block_text(group_id)
    if inv_block:
        return False, inv_block

    # 归西复活检查（复活时间到则自动复活）
    combat.try_revive(group_id, user_id)
    player = db.get_player(group_id, user_id)
    if combat.is_dead(player):
        return False, f"你已归西，气血归零无法修炼！还需 {combat.dead_remain_seconds(player)} 秒复活"
    if combat.get_cur_hp(player) <= 0:
        return False, "你气血耗尽，无法修炼！服用回灵丹/大还丹恢复气血"

    if debuff.block_cultivate(player):
        blocker = next(
            (d for d in debuff.get_active_debuffs(player) if d.get("block_cultivate")),
            None,
        )
        name = blocker["name"] if blocker else "走火入魔"
        return False, f"你正处于【{name}】状态，无法闭关！"

    if db.get_cultivation(group_id, user_id):
        return False, "你正在闭关修炼中，先「出关」吧"

    # 已拜入师门的弟子无法修炼
    if db.get_furnace_by_target(group_id, user_id):
        return False, "你已是他人弟子，无法自主修炼！发送「叛门」尝试脱离师门"

    if location not in constants.LOCATIONS:
        return False, f"未知修炼地点，可选：{'、'.join(constants.LOCATIONS.keys())}"

    if not world.is_location_open(group_id, location):
        event_name = world.location_open_event(location)
        if event_name:
            return False, f"{location}尚未开启，等待「{event_name}」事件出现吧"
        return False, f"{location}尚未开启"

    if not db.start_cultivation(group_id, user_id, location):
        return False, "开始修炼失败，请稍后再试"

    return True, location


def settle_cultivation(group_id: int, user_id: int) -> dict:
    """结算闭关收益，返回结算结果 dict"""
    player = db.get_player(group_id, user_id)
    cult = db.get_cultivation(group_id, user_id)
    if not player or not cult:
        return {"ok": False, "text": "当前没有进行中的闭关"}

    location = cult["location"]
    elapsed_sec = time.time() - cult["started_at"]
    elapsed_hours = elapsed_sec / 3600.0
    db.end_cultivation(group_id, user_id)

    rate = calculate_rate(group_id, player, location)
    progress = rate * elapsed_hours

    result = {
        "ok": True,
        "user_id": user_id,
        "location": location,
        "hours": round(elapsed_hours, 2),
        "rate": round(rate, 1),
        "progress": 0.0,
        "coins": 0,
        "healed_full": False,
        "risk_failed": False,
        "risk_text": "",
        "enlighten": False,
        "gongfa_levelup": [],
    }

    # 闭关满一定时长，出关后气血回满（静养恢复）
    if elapsed_sec >= config.cultivation_heal_minutes * 60:
        heal = combat.heal_full(group_id, user_id)
        result["healed_full"] = True
        result["healed_hp"] = f"{heal['hp']}/{heal['max_hp']}"

    # 失败判定（遇险）：气运越高越容易避开危险，遇险会扣除气血
    risk = _location_risk(group_id, location)
    if rng.risk_roll(risk, player.get("fortune", 1000)):
        lost = progress * 0.3
        progress -= lost
        result["risk_failed"] = True
        result["risk_text"] = f"⚠️ 修炼途中遭遇{random.choice(['妖兽突袭', '灵气暴乱', '心魔入侵'])}，损失部分修为！"
        dmg = combat.apply_negative_damage(group_id, user_id)
        result["risk_text"] += f"\n🩸 {dmg['text']}"

    # 顿悟判定（气运越高越容易触发，道韵弥漫事件额外加成；太虚灵体翻倍）
    enlighten_chance = constants.ENLIGHTEN_CHANCE + world.enlighten_bonus(group_id)
    if player.get("physique") == "taixu_lt":
        enlighten_chance *= 2
    if rng.luck_roll(enlighten_chance, player.get("fortune", 1000)):
        bonus = constants.ENLIGHTEN_PROGRESS * (1 + rng.fortune_factor(player.get("fortune", 1000)) * 2)
        progress += bonus
        result["enlighten"] = True
        result["risk_text"] = (result["risk_text"] + "\n" if result["risk_text"] else "") + "💡 悟道顿悟，额外获得大量修为！"

    # 闭关过久，可能走火入魔（禁止修炼一段时间 + 损失修为）
    if elapsed_hours >= config.zouhuo_cultivate_hours:
        if rng.luck_roll(constants.DEBUFF_TRIGGER["zouhuo"], player.get("fortune", 1000)):
            d = debuff.add_debuff(group_id, user_id, "zouhuo_rumo")
            lost = int(progress * 0.05)
            progress -= lost
            result["risk_failed"] = True
            result["risk_text"] = (result["risk_text"] + "\n" if result["risk_text"] else "") + (
                f"🔥 闭关过久气血逆行，走火入魔！【{d['name']}】缠身，损失 {lost} 修为，暂时无法闭关！"
            )

    # 负面状态持续掉血（如丹药中毒）
    tick = debuff.damage_per_hour(player)
    if tick > 0:
        dmg = int(tick * elapsed_hours)
        if dmg > 0:
            combat.take_damage(group_id, user_id, dmg)
            result["risk_text"] = (result["risk_text"] + "\n" if result["risk_text"] else "") + f"🩸 体内淤毒发作，损失 {dmg} 点气血！"

    # 修为结算（不超过当前境界容量）
    realm_index = player.get("realm", 0)
    capacity = constants.REALMS[realm_index]["capacity"]
    current = player.get("realm_progress", 0) + progress
    if capacity:
        current = min(current, capacity)
    db.update_player(group_id, user_id, {"realm_progress": current})
    result["progress"] = progress
    result["total_progress"] = current

    # 灵石收益：每小时 = 基础 5 + 修炼速率 * 0.1（财源广进体收益+50%）
    coins = int(elapsed_hours * (constants.COIN_PER_HOUR_BASE + rate * constants.COIN_PER_RATE))
    if player.get("physique") == "caiyuan_ti":
        coins = int(coins * 1.5)
    if coins > 0:
        db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + coins})
        result["coins"] = coins

    # 功法熟练度成长（武痴圣体+50%）
    gongfa_exp = elapsed_hours * 15 * (1 + constants.QUALITIES.get(player.get("spirit_quality", "废品"), 0.05))
    if player.get("physique") == "wuchi_st":
        gongfa_exp *= 1.5
    for g in db.get_gongfas(group_id, user_id):
        old, new = add_gongfa_exp(group_id, user_id, g["gongfa_id"], gongfa_exp)
        if new > old:
            info = constants.GONGFA_BY_ID.get(g["gongfa_id"], {})
            result["gongfa_levelup"].append(f"{info.get('name', g['gongfa_id'])}→{constants.PROFICIENCIES[new]}")

    return result


def format_settle_result(group_id: int, result: dict) -> str:
    """格式化出关结算文本"""
    player = db.get_player(group_id, result.get("user_id", 0))
    realm_name = constants.REALMS[player["realm"]]["name"] if player else ""
    lines = [
        f"⛰️ 【出关结算】{realm_name}",
        f"📍 修炼地点：{result['location']}",
        f"⏱️ 闭关时长：{result['hours']} 小时",
        f"📈 修炼速率：{result['rate']} 修为/小时",
        f"✨ 获得修为：{int(result['progress'])}",
    ]
    if result.get("coins"):
        lines.append(f"💰 获得灵石：{result['coins']}")
    if result.get("healed_full"):
        lines.append(f"💚 静养恢复：气血回满（{result.get('healed_hp', '')}）")
    if result.get("risk_text"):
        lines.append(result["risk_text"])
    if result.get("gongfa_levelup"):
        lines.append("📜 功法领悟：" + "、".join(result["gongfa_levelup"]))
    lines.append(f"💠 当前修为：{int(result.get('total_progress', 0))}")
    return "\n".join(lines)

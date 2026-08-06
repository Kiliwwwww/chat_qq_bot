"""挂机修炼系统。

玩家「闭关」后离线挂机，再次「出关」时根据离线时长结算收益。
"""

import random
import time

from .. import constants
from ..state import config, db
from . import rng, world


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

    # 灵宠加成
    pet_bonus = sum(
        constants.PET_TYPE_BY_ID.get(p["pet_type"], {}).get("rate", 0.0) * p.get("level", 1)
        for p in db.get_pets(group_id, player["user_id"])
    )

    # 炉鼎加成（紫金炉体加速翻倍且上限+1；玄阴鼎炉被抓时主人受益翻倍）
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

    rate = (
        constants.BASE_CULTIVATION_RATE
        * quality_mult
        * location_mult
        * world_mult
        * (1 + gongfa_bonus + physique_bonus + pet_bonus + furnace_bonus)
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

    if db.get_cultivation(group_id, user_id):
        return False, "你正在闭关修炼中，先「出关」吧"

    # 炉鼎状态无法修炼
    if db.get_furnace_by_target(group_id, user_id):
        return False, "你已沦为他人炉鼎，无法自主修炼！发送「挣脱」尝试反抗"

    if location not in constants.LOCATIONS:
        return False, f"未知修炼地点，可选：{'、'.join(constants.LOCATIONS.keys())}"

    if location == "秘境" and not world.is_secret_realm_open(group_id):
        return False, "秘境尚未开启，等待「上古秘境」事件出现吧"

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
        "risk_failed": False,
        "risk_text": "",
        "enlighten": False,
        "gongfa_levelup": [],
    }

    # 失败判定（遇险）：气运越高越容易避开危险
    risk = _location_risk(group_id, location)
    if rng.risk_roll(risk, player.get("fortune", 1000)):
        lost = progress * 0.3
        progress -= lost
        result["risk_failed"] = True
        result["risk_text"] = f"⚠️ 修炼途中遭遇{random.choice(['妖兽突袭', '灵气暴乱', '心魔入侵'])}，损失部分修为！"

    # 顿悟判定（气运越高越容易触发）
    if rng.luck_roll(constants.ENLIGHTEN_CHANCE, player.get("fortune", 1000)):
        bonus = constants.ENLIGHTEN_PROGRESS * (1 + rng.fortune_factor(player.get("fortune", 1000)) * 2)
        progress += bonus
        result["enlighten"] = True
        result["risk_text"] = (result["risk_text"] + "\n" if result["risk_text"] else "") + "💡 悟道顿悟，额外获得大量修为！"

    # 修为结算（不超过当前境界容量）
    realm_index = player.get("realm", 0)
    capacity = constants.REALMS[realm_index]["capacity"]
    current = player.get("realm_progress", 0) + progress
    if capacity:
        current = min(current, capacity)
    db.update_player(group_id, user_id, {"realm_progress": current})
    result["progress"] = progress
    result["total_progress"] = current

    # 功法熟练度成长
    gongfa_exp = elapsed_hours * 15 * (1 + constants.QUALITIES.get(player.get("spirit_quality", "废品"), 0.05))
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
    if result.get("risk_text"):
        lines.append(result["risk_text"])
    if result.get("gongfa_levelup"):
        lines.append("📜 功法领悟：" + "、".join(result["gongfa_levelup"]))
    lines.append(f"💠 当前修为：{int(result.get('total_progress', 0))}")
    return "\n".join(lines)

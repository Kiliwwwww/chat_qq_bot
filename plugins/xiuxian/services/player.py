"""角色创建系统。

支持两种开局：
- 随机天命：随机灵根、品质、体质、气运
- 废材流主角：空灵根/废品/高气运，前期弱后期强
"""

import random

from nonebot import logger

from .. import constants
from ..state import db
from . import rng


def build_base_stats(spirit_root: str, trash: bool = False) -> dict:
    """根据灵根计算基础属性"""
    root = constants.SPIRIT_ROOTS[spirit_root]
    if trash:
        # 废材流基础属性较差
        return {"attack": 8, "defense": 8, "hp": 80}
    attr = root["attr"]
    return {
        "attack": max(1, int(constants.BASE_ATTACK * attr["attack"])),
        "defense": max(1, int(constants.BASE_DEFENSE * attr["defense"])),
        "hp": max(10, int(constants.BASE_HP * attr["hp"])),
    }


def pick_starter_gongfa(spirit_root: str) -> dict:
    """为创建的角色挑选一本初始功法"""
    if spirit_root == "空":
        pool = [g for gongfas in constants.GONGFAS.values() for g in gongfas]
    else:
        pool = constants.GONGFAS[spirit_root]
    return random.choice(pool)


def create_character(group_id: int, user_id: int, name: str, talent: str) -> tuple[bool, str, dict]:
    """创建角色。

    talent: random(随机天命) / trash(废材流主角)
    返回 (是否成功, 消息, 玩家数据)
    """
    if db.get_player(group_id, user_id):
        return False, "你已经踏上修仙之路了！", {}

    if talent == "trash":
        spirit_root = "空"
        spirit_quality = "废品"
        fortune = constants.TRASH_FORTUNE
        physique = ""
        base_stats = build_base_stats(spirit_root, trash=True)
        phys_text = ""
        if random.random() < 0.05:
            physique = rng.weighted_choice(constants.PHYSIQUES)["id"]
    else:
        spirit_root = rng.weighted_choice_dict(constants.SPIRIT_ROOT_WEIGHTS)
        spirit_quality = rng.weighted_choice_dict(constants.QUALITY_WEIGHTS)
        fortune = constants.DEFAULT_FORTUNE
        base_stats = build_base_stats(spirit_root)
        physique = ""
        if random.random() < constants.PHYSIQUE_CHANCE:
            physique = rng.weighted_choice(constants.PHYSIQUES)["id"]

    starter = pick_starter_gongfa(spirit_root)

    player_data = {
        "name": name,
        "realm": 0,
        "realm_progress": 0,
        "spirit_root": spirit_root,
        "spirit_quality": spirit_quality,
        "fortune": fortune,
        "physique": physique,
        "talent": talent,
        "attack": base_stats["attack"],
        "defense": base_stats["defense"],
        "hp": base_stats["hp"],
        "coin": 100,
        "alchemy_level": 1,
        "forge_level": 1,
    }
    ok = db.create_player(group_id, user_id, player_data)
    if not ok:
        return False, "创建角色失败，请稍后再试", {}
    db.learn_gongfa(group_id, user_id, starter["id"])
    return True, "", player_data


def get_or_create_name(event_name: str, user_id: int) -> str:
    """生成角色名（使用群名片或QQ号）"""
    return event_name or str(user_id)


def change_physique(group_id: int, user_id: int, target_name: str = "") -> dict:
    """花费大量灵石更换特殊体质。

    target_name 为空时随机重铸；指定名称时直接更换为目标体质（费用更高）。
    """
    from ..state import config

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    current_physique = player.get("physique", "")

    # 计算费用（境界越高越贵）
    realm = player.get("realm", 0)

    if target_name:
        target = constants.PHYSIQUE_BY_NAME.get(target_name)
        if not target:
            return {"ok": False, "text": f"没有叫「{target_name}」的体质，可用体质：{'、'.join(p['name'] for p in constants.PHYSIQUES)}"}
        if current_physique == target["id"]:
            return {"ok": False, "text": f"你当前就是【{target['name']}】，无需更换"}
        cost = config.change_physique_cost * 3 * (1 + realm)
    else:
        # 随机重铸，避开当前体质
        pool = [p for p in constants.PHYSIQUES if p["id"] != current_physique]
        target = rng.weighted_choice(pool)
        cost = config.change_physique_cost * (1 + realm)

    if player.get("coin", 0) < cost:
        return {"ok": False, "text": f"灵石不足！更换体质需要 {cost} 灵石（当前 {player.get('coin', 0)}）"}

    db.update_player(group_id, user_id, {
        "physique": target["id"],
        "coin": player.get("coin", 0) - cost,
    })
    logger.info(f"玩家更换体质 group={group_id} user={user_id} -> {target['name']}（花费 {cost} 灵石）")

    text = (
        f"✨ 【体质更换成功】花费 {cost} 灵石！\n"
        f"获得特殊体质【{target['name']}】\n"
        f"💬 {target['desc']}"
    )
    return {"ok": True, "text": text}


def format_player_profile(group_id: int, player: dict, gongfa_text: str = "") -> str:
    """格式化玩家面板"""
    root = constants.SPIRIT_ROOTS.get(player["spirit_root"], {})
    realm_name = constants.REALMS[player["realm"]]["name"]
    capacity = constants.REALMS[player["realm"]]["capacity"]

    lines = [
        f"📜 【修仙面板】{player.get('name', '')}",
        f"🔰 境界：{realm_name}（修为 {int(player.get('realm_progress', 0))}/{int(capacity) if capacity else '∞'}）",
        f"⚡ 灵根：{root.get('name', player['spirit_root'])}（{player['spirit_quality']}）",
        f"🍀 气运：{player.get('fortune', 0)}",
        f"⚔️ 攻击：{player.get('attack', 0)}  🛡️ 防御：{player.get('defense', 0)}  ❤️ 气血：{player.get('hp', 0)}",
        f"💰 灵石：{player.get('coin', 0)}",
        f"🏃 天命：{'随机天命' if player.get('talent') != 'trash' else '废材流主角'}",
    ]
    if player.get("physique"):
        phys = constants.PHYSIQUE_BY_ID.get(player["physique"], {})
        lines.append(f"✨ 体质：{phys.get('name', player['physique'])} - {phys.get('desc', '')}")
    if gongfa_text:
        lines.append(gongfa_text)
    return "\n".join(lines)

"""战力与属性计算服务。"""

from typing import Optional

from .. import constants
from ..state import db


def _parse_equip(item_id: str) -> Optional[tuple[str, str]]:
    """解析装备物品 ID：equip:<kind>:<quality>"""
    if not item_id:
        return None
    parts = item_id.split(":")
    if len(parts) == 3 and parts[0] == "equip":
        return parts[1], parts[2]
    return None


def get_effective_stats(group_id: int, player: dict, gongfas: Optional[list[dict]] = None) -> dict:
    """计算玩家最终属性（基础 + 功法 + 装备 + 体质）"""
    base_attack = player.get("attack", 0)
    base_defense = player.get("defense", 0)
    base_hp = player.get("hp", 0)

    if gongfas is None:
        gongfas = db.get_gongfas(group_id, player["user_id"])

    attack = base_attack
    defense = base_defense
    hp = base_hp

    # 功法加成
    for g in gongfas:
        info = constants.GONGFA_BY_ID.get(g["gongfa_id"])
        if not info:
            continue
        mult = constants.PROFICIENCY_MULT[g.get("level", 0)]
        bonus = info["bonus"] * mult
        if info["attr"] == "attack":
            attack += base_attack * bonus
        elif info["attr"] == "defense":
            defense += base_defense * bonus
        elif info["attr"] == "hp":
            hp += base_hp * bonus
        # cultivation 类功法不直接加属性

    # 装备加成
    for slot in ("weapon", "armor", "treasure"):
        item_id = player.get(slot, "")
        parsed = _parse_equip(item_id)
        if not parsed:
            continue
        _, quality = parsed
        kind = constants.EQUIPMENT_KINDS.get(slot)
        if not kind:
            continue
        stat = kind["stat"]
        quality_mult = 1.0
        for q in constants.EQUIPMENT_QUALITIES:
            if q["name"] == quality:
                quality_mult = q["mult"]
                break
        if stat == "attack":
            attack += base_attack * quality_mult * 0.5
        elif stat == "defense":
            defense += base_defense * quality_mult * 0.5
        elif stat == "hp":
            hp += base_hp * quality_mult * 0.5

    # 体质加成
    physique = player.get("physique", "")
    if physique == "tiansheng_jt":
        attack = int(attack * 1.2)
    elif physique == "huanggu_sgt":
        defense = int(defense * 1.15)
        hp = int(hp * 1.15)
    elif physique == "jianxin_tm":
        attack = int(attack * 1.4)
    elif physique == "hundun_ti":
        attack = int(attack * 1.25)
        defense = int(defense * 1.25)
        hp = int(hp * 1.25)

    return {
        "attack": int(attack),
        "defense": int(defense),
        "hp": int(hp),
    }


def get_power(group_id: int, player: dict) -> int:
    """计算玩家战力"""
    stats = get_effective_stats(group_id, player)
    realm_mult = constants.REALM_POWER_MULT.get(player.get("realm", 0), 1)
    power = (stats["attack"] * 10 + stats["defense"] * 8 + stats["hp"]) * realm_mult
    return int(power)

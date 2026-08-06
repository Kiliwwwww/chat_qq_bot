"""角色创建系统。

支持两种开局：
- 随机天命：随机灵根、品质、体质、气运
- 废材流主角：空灵根/废品/高气运，前期弱后期强
"""

import random

from nonebot import logger

from .. import constants
from ..state import config, db
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
        # 废材流主角必定觉醒一种随机特殊体质（逆袭设定）
        physique = rng.weighted_choice(constants.PHYSIQUES)["id"]
        base_stats = build_base_stats(spirit_root, trash=True)
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
        "cur_hp": base_stats["hp"],
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
        f"⚔️ 攻击：{player.get('attack', 0)}  🛡️ 防御：{player.get('defense', 0)}  ❤️ 气血上限：{player.get('hp', 0)}",
        f"💰 灵石：{player.get('coin', 0)}",
        f"🏃 天命：{'随机天命' if player.get('talent') != 'trash' else '废材流主角'}",
    ]
    # 血量与归西状态
    from . import combat
    max_hp = combat.get_max_hp(player)
    cur_hp = combat.get_cur_hp(player)
    if combat.is_dead(player):
        lines.append(f"💀 状态：归西（{combat.dead_remain_seconds(player)} 秒后复活）")
    else:
        lines.append(f"🩸 血量：{cur_hp}/{max_hp}")
    if player.get("pk_boost", 0):
        lines.append(f"💥 狂暴之力：下次 PK 战力 +{int(player['pk_boost'] * 100)}%")
    if player.get("rebirth_count"):
        lines.append(f"🌀 转世：{player.get('rebirth_count')} 次（修炼速率永久 +{int(player.get('rebirth_count', 0) * config.rebirth_rate_bonus * 100)}%）")
    if player.get("physique"):
        phys = constants.PHYSIQUE_BY_ID.get(player["physique"], {})
        lines.append(f"✨ 体质：{phys.get('name', player['physique'])} - {phys.get('desc', '')}")
    if gongfa_text:
        lines.append(gongfa_text)
    return "\n".join(lines)


def rebirth(group_id: int, user_id: int) -> dict:
    """转世重生：重置角色数据，保留灵根/品质/体质/天命，获得永久气运与修炼加成。"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    # 转世门槛
    if player.get("realm", 0) < config.rebirth_min_realm:
        required_name = constants.REALMS[config.rebirth_min_realm]["name"]
        return {"ok": False, "text": f"转世重生需要至少达到【{required_name}】境界（当前{constants.REALMS[player['realm']]['name']}）"}

    # 清除关联数据（功法/背包/灵宠/炉鼎/挂机/冷却）
    if not db.reset_player_related(group_id, user_id):
        return {"ok": False, "text": "转世失败，请稍后再试"}

    rebirth_count = player.get("rebirth_count", 0) + 1
    new_fortune = player.get("fortune", 1000) + config.rebirth_fortune_bonus

    # 重置基础属性（废材流保留低属性起步）
    base_stats = build_base_stats(player["spirit_root"], trash=(player.get("talent") == "trash"))

    # 重新领悟初始功法
    starter = pick_starter_gongfa(player["spirit_root"])
    db.learn_gongfa(group_id, user_id, starter["id"])

    db.update_player(group_id, user_id, {
        "realm": 0,
        "realm_progress": 0,
        "attack": base_stats["attack"],
        "defense": base_stats["defense"],
        "hp": base_stats["hp"],
        "coin": config.rebirth_coin,
        "alchemy_level": 1,
        "alchemy_exp": 0,
        "forge_level": 1,
        "forge_exp": 0,
        "bottleneck_until": 0,
        "weapon": "",
        "armor": "",
        "treasure": "",
        "ring": "",
        "boots": "",
        "cur_hp": base_stats["hp"],
        "dead_until": 0,
        "pk_boost": 0,
        "pk_hp_cost": 0,
        "fortune": new_fortune,
        "rebirth_count": rebirth_count,
    })
    logger.info(f"玩家转世重生 group={group_id} user={user_id} 第 {rebirth_count} 世")

    text = (
        f"🌀 【转世重生】你已历经 {rebirth_count} 世轮回！\n"
        f"保留灵根【{constants.SPIRIT_ROOTS[player['spirit_root']]['name']}】（{player['spirit_quality']}）"
        f"{'与特殊体质【' + constants.PHYSIQUE_BY_ID[player['physique']]['name'] + '】' if player.get('physique') else ''}\n"
        f"🍀 气运 +{config.rebirth_fortune_bonus}（现 {new_fortune}）\n"
        f"📈 修炼速率永久 +{int(config.rebirth_rate_bonus * 100)}%（累计 +{int(rebirth_count * config.rebirth_rate_bonus * 100)}%）\n"
        f"所有修为、功法、背包、灵宠、炉鼎均已归零，重新踏上仙途吧！"
    )
    return {"ok": True, "text": text}


def suicide(group_id: int, user_id: int) -> dict:
    """自杀：彻底删除角色全部数据，不保留任何内容。"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，无法自杀"}

    if not db.delete_player(group_id, user_id):
        return {"ok": False, "text": "自杀失败，请稍后再试"}

    logger.info(f"玩家自杀清空数据 group={group_id} user={user_id}")
    return {"ok": True, "text": "💀 你已兵解自杀，魂飞魄散！\n所有角色数据已被彻底清空，不再留有任何痕迹。\n若想东山再起，发送「我要修仙」重新开始。"}

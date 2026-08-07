"""世界 Boss 系统。

Boss 随机刷新在群内，实力按群内最强玩家战力定（比最强玩家强一点）。
全群玩家可讨伐，Boss 死亡后按伤害贡献分配奖励，超时则逃脱。
"""

import random
import time

from .. import constants
from ..state import config, db
from . import combat, debuff, rng, stats, world


def get_strongest_power(group_id: int) -> int:
    """群内最强玩家战力"""
    players = db.execute_raw("SELECT user_id FROM players WHERE group_id = ?", (group_id,))
    best = 0
    for r in players:
        p = db.get_player(group_id, r["user_id"])
        if p:
            power = stats.get_power(group_id, p)
            if power > best:
                best = power
    return best


def get_active_boss(group_id: int) -> dict | None:
    """获取当前存活中的 Boss，过期则清除并返回 None"""
    boss = db.get_world_boss(group_id)
    if not boss:
        return None
    if time.time() >= boss["expire_time"]:
        db.clear_world_boss(group_id)
        return None
    return boss


def maybe_spawn(group_id: int) -> dict | None:
    """按概率刷新世界 Boss，成功返回公告文本。"""
    if get_active_boss(group_id):
        return None
    if random.random() >= constants.BOSS_SPAWN_CHANCE:
        return None

    strongest = get_strongest_power(group_id)
    if strongest <= 0:
        return None  # 群里没有玩家，不刷新

    max_hp = max(constants.BOSS_MIN_MAX_HP, int(strongest * constants.BOSS_MAX_HP_FACTOR))
    attack = max(50, int(strongest * constants.BOSS_ATTACK_FACTOR))
    now = time.time()
    boss = {
        "boss_id": f"boss_{int(now)}_{random.randint(1000, 9999)}",
        "name": random.choice(constants.BOSS_NAMES),
        "hp": float(max_hp),
        "max_hp": float(max_hp),
        "attack": attack,
        "spawn_time": now,
        "expire_time": now + constants.BOSS_LIFETIME_MINUTES * 60,
    }
    db.spawn_world_boss(group_id, boss)
    return f"🌋 【世界BOSS】{boss['name']} 现身！\n💢 血量 {int(boss['max_hp'])}，攻击 {attack}\n⏳ {constants.BOSS_LIFETIME_MINUTES} 分钟内请群仙讨伐！发送「讨伐boss」参战"


def attack_boss(group_id: int, user_id: int) -> dict:
    """玩家讨伐 Boss"""
    boss = get_active_boss(group_id)
    if not boss:
        return {"ok": False, "text": "当前没有世界 Boss，等待刷新吧"}

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if combat.is_dead(player):
        return {"ok": False, "text": f"你已归西，还需 {combat.dead_remain_seconds(player)} 秒复活，无法讨伐"}

    # 讨伐冷却
    record = db.get_boss_damage(group_id, user_id)
    last_attack = record["last_attack"] if record else 0
    if time.time() - last_attack < constants.BOSS_ATTACK_COOLDOWN:
        remain = int(constants.BOSS_ATTACK_COOLDOWN - (time.time() - last_attack))
        return {"ok": False, "text": f"讨伐消耗心神，还需 {remain} 秒才能再次出手"}

    # 玩家伤害 = 战力 × 随机比例 × 气运加成（灵气潮汐事件期间增伤）
    power = stats.get_power(group_id, player)
    dmg_ratio = random.uniform(constants.BOSS_DMG_MIN, constants.BOSS_DMG_MAX)
    dmg = power * dmg_ratio * (1 + rng.fortune_factor(debuff.effective_fortune(player)))
    if world.get_current_event(group_id).get("name") == "灵气潮汐":
        dmg *= constants.BOSS_EVENT_DAMAGE_MULT
    dmg = max(1, int(dmg))

    # Boss 反击：玩家受到伤害（系数偏低，保证玩家能扛 1-2 下再回血）
    counter = max(1, int(boss["attack"] * random.uniform(0.3, 0.6)))
    hit = combat.take_damage(group_id, user_id, counter)

    # 扣 Boss 血并记录贡献
    db.add_boss_damage(group_id, user_id, dmg)
    new_hp = boss["hp"] - dmg

    hit_text = f"你受到反击，损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）"
    if hit["died"]:
        hit_text = f"💀 你被 {boss['name']} 反击致死，魂归西天！"

    if new_hp <= 0:
        new_hp = 0
        db.update_world_boss(group_id, {"hp": new_hp, "last_hitter": user_id})
        kill_text = _grant_rewards(group_id, boss)
        return {
            "ok": True,
            "text": f"⚔️ 你向 {boss['name']} 造成 {dmg} 伤害！\n💢 气血耗尽！Boss 被击败！\n{hit_text}\n{kill_text}",
        }

    db.update_world_boss(group_id, {"hp": new_hp})
    return {
        "ok": True,
        "text": (
            f"⚔️ 你向 {boss['name']} 造成 {dmg} 伤害！\n"
            f"💢 Boss 剩余气血：{int(new_hp)}/{int(boss['max_hp'])}\n"
            f"{hit_text}"
        ),
    }


def check_expire(group_id: int) -> str | None:
    """检查 Boss 是否超时逃脱，返回公告文本。"""
    boss = db.get_world_boss(group_id)
    if not boss:
        return None
    if time.time() >= boss["expire_time"]:
        db.clear_world_boss(group_id)
        return f"🌫️ 【世界BOSS】{boss['name']} 久攻不下，遁走逃跑了！"
    return None


def format_boss_status(group_id: int) -> str:
    """查看当前 Boss 状态"""
    boss = get_active_boss(group_id)
    if not boss:
        return "🌋 当前没有世界 Boss，稍后可能会随机刷新（发送「讨伐boss」参与）"
    remain = int((boss["expire_time"] - time.time()) / 60)
    return (
        f"🌋 【世界BOSS】{boss['name']}\n"
        f"💢 气血：{int(boss['hp'])}/{int(boss['max_hp'])}\n"
        f"⚔️ 攻击：{boss['attack']}\n"
        f"⏳ 剩余 {max(remain, 0)} 分钟\n"
        f"📊 当前贡献：\n" + format_contributions(group_id)
    )


def format_contributions(group_id: int) -> str:
    contribs = db.get_boss_contributions(group_id)
    if not contribs:
        return "  （暂无玩家讨伐）"
    lines = []
    for c in contribs[:5]:
        p = db.get_player(group_id, c["user_id"])
        name = p["name"] if p else str(c["user_id"])
        lines.append(f"  · {name}：{int(c['total_damage'])} 伤害")
    return "\n".join(lines)


def _grant_rewards(group_id: int, boss: dict) -> str:
    """Boss 击杀后发放奖励，返回公告文本"""
    contribs = db.get_boss_contributions(group_id)
    total_damage = sum(c["total_damage"] for c in contribs) or 1
    last_hitter = db.get_world_boss(group_id)["last_hitter"] if db.get_world_boss(group_id) else 0

    pool = int(boss["max_hp"] * constants.BOSS_SHARE_POOL_FACTOR)
    lines = ["🏆 【讨伐成功】奖励结算："]
    for c in contribs:
        uid = c["user_id"]
        p = db.get_player(group_id, uid)
        if not p:
            continue
        share = int(pool * c["total_damage"] / total_damage)
        coins = constants.BOSS_REWARD_BASE + share
        if uid == last_hitter:
            coins += constants.BOSS_REWARD_LAST_HIT
        progress = int(stats.get_power(group_id, p) * constants.BOSS_PROGRESS_REWARD)
        db.update_player(group_id, uid, {
            "coin": p.get("coin", 0) + coins,
            "realm_progress": _add_progress_capped(group_id, p, progress),
        })
        name = p["name"] or str(uid)
        lines.append(f"  · {name}：灵石 +{coins}，修为 +{progress}")

    # MVP
    if contribs:
        mvp = contribs[0]
        mp = db.get_player(group_id, mvp["user_id"])
        if mp:
            db.update_player(group_id, mvp["user_id"], {"coin": mp.get("coin", 0) + constants.BOSS_REWARD_MVP})
            lines.append(f"  🥇 MVP：{mp['name']} 额外获得 {constants.BOSS_REWARD_MVP} 灵石！")

    db.clear_world_boss(group_id)
    return "\n".join(lines)


def _add_progress_capped(group_id: int, player: dict, progress: int) -> float:
    realm_index = player.get("realm", 0)
    capacity = constants.REALMS[realm_index]["capacity"]
    current = player.get("realm_progress", 0) + progress
    if capacity:
        current = min(current, capacity)
    return current

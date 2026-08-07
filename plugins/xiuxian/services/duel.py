"""生死台系统。

玩家发送「开启生死台 @对方」向对方发起生死决斗，对方发送「同意生死台」应战后，
双方自动进行多回合对决，直到一方气血耗尽归西为止。
输家损失灵石与修为，赢家获得对方损失的灵石。
"""

import random
import time

from .. import constants
from ..state import db, get_cache
from . import combat, debuff, rng, stats


def _cache_key(group_id: int, target_id: int) -> str:
    """待应战挑战缓存键：target 当前收到的挑战发起者"""
    return f"{group_id}:duel_challenge:{target_id}"


def _cooldown_key(group_id: int, user_id: int) -> str:
    """决斗冷却缓存键"""
    return f"{group_id}:duel_cooldown:{user_id}"


async def challenge(group_id: int, challenger_id: int, target_id: int) -> dict:
    """发起生死台挑战"""
    if challenger_id == target_id:
        return {"ok": False, "text": "不能向自己发起生死台挑战"}

    challenger = db.get_player(group_id, challenger_id)
    target = db.get_player(group_id, target_id)
    if not challenger:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if not target:
        return {"ok": False, "text": "对方没有修仙角色，无法发起挑战"}
    if combat.is_dead(challenger):
        return {"ok": False, "text": f"你已归西，还需 {combat.dead_remain_seconds(challenger)} 秒复活，无法发起挑战"}
    if combat.is_dead(target):
        return {"ok": False, "text": "对方正在归西状态，无法发起挑战"}

    # 挑战冷却
    cache = get_cache()
    cooldown = await cache.get(_cooldown_key(group_id, challenger_id))
    if cooldown and time.time() < cooldown:
        remain = int(cooldown - time.time())
        return {"ok": False, "text": f"你刚进行过生死台决斗，还需 {remain} 秒才能再次发起"}

    # 已有待应战挑战
    cache_key = _cache_key(group_id, target_id)
    existing = await cache.get(cache_key)
    if existing:
        return {"ok": False, "text": "对方已有待应战的生死台挑战，请等待对方回应"}

    await cache.set(cache_key, challenger_id, expire=constants.DUEL_CHALLENGE_EXPIRE)

    target_name = target.get("name") or str(target_id)
    challenger_name = challenger.get("name") or str(challenger_id)
    return {
        "ok": True,
        "text": (
            f"🏯 【生死台挑战】\n"
            f"⚔️ {challenger_name} 向 {target_name} 发起生死台挑战！\n"
            f"💀 上得生死台，至死方休！\n"
            f"💡 请 {target_name} 发送「同意生死台」应战"
            f"（{constants.DUEL_CHALLENGE_EXPIRE // 60} 分钟内有效）"
        ),
    }


async def accept(group_id: int, user_id: int) -> dict:
    """应战生死台"""
    cache = get_cache()
    cache_key = _cache_key(group_id, user_id)
    challenger_id = await cache.get(cache_key)
    if not challenger_id:
        return {"ok": False, "text": "你当前没有待应战的生死台挑战"}

    player = db.get_player(group_id, user_id)
    challenger = db.get_player(group_id, challenger_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if not challenger:
        await cache.delete(cache_key)
        return {"ok": False, "text": "挑战方已无修仙角色，挑战失效"}
    if combat.is_dead(player):
        return {"ok": False, "text": f"你已归西，还需 {combat.dead_remain_seconds(player)} 秒复活，无法应战"}
    if combat.is_dead(challenger):
        await cache.delete(cache_key)
        return {"ok": False, "text": "挑战方正在归西状态，挑战失效"}

    # 应战冷却
    cooldown = await cache.get(_cooldown_key(group_id, user_id))
    if cooldown and time.time() < cooldown:
        remain = int(cooldown - time.time())
        return {"ok": False, "text": f"你刚进行过生死台决斗，还需 {remain} 秒才能再次应战"}

    # 清除待应战挑战
    await cache.delete(cache_key)

    # 决斗前双方回满气血，公平对决
    combat.heal_full(group_id, challenger_id)
    combat.heal_full(group_id, user_id)

    return await run_duel(group_id, challenger_id, user_id)


def _round_text(winner: dict, loser: dict, dmg: int, loser_hp: int, loser_max: int, round_no: int) -> str:
    """生成单回合文案"""
    w_name = winner.get("name") or str(winner["user_id"])
    l_name = loser.get("name") or str(loser["user_id"])
    texts = [
        f"⚔️ 第{round_no}回合：{w_name} 剑光暴涨，一击命中 {l_name}！",
        f"⚔️ 第{round_no}回合：{w_name} 催动真元，掌风呼啸劈向 {l_name}！",
        f"⚔️ 第{round_no}回合：{w_name} 身法如电，重创 {l_name}！",
        f"⚔️ 第{round_no}回合：{w_name} 周身金光大盛，硬生生轰飞 {l_name}！",
        f"⚔️ 第{round_no}回合：{w_name} 一道剑意横空，正中 {l_name}！",
        f"⚔️ 第{round_no}回合：{w_name} 施展绝学，杀得 {l_name} 节节败退！",
    ]
    return f"{random.choice(texts)}（-{dmg} 气血，{l_name} 剩余 {max(0, loser_hp)}/{loser_max}）"


async def run_duel(group_id: int, a_id: int, b_id: int) -> dict:
    """自动多回合生死对决，直到一方归西"""
    a = db.get_player(group_id, a_id)
    b = db.get_player(group_id, b_id)
    if not a or not b:
        return {"ok": False, "text": "决斗失败，有一方已无角色"}

    a_name = a.get("name") or str(a_id)
    b_name = b.get("name") or str(b_id)
    a_max = combat.get_max_hp(a)
    b_max = combat.get_max_hp(b)
    a_hp = combat.get_cur_hp(a)
    b_hp = combat.get_cur_hp(b)

    logs = [f"🏯 【生死台】{a_name} vs {b_name}，不死不休！"]
    winner_id = 0
    loser_id = 0

    for round_no in range(1, constants.DUEL_MAX_ROUNDS + 1):
        pa = stats.get_power(group_id, a)
        pb = stats.get_power(group_id, b)
        chance_a = pa / (pa + pb)
        chance_a += rng.fortune_factor(debuff.effective_fortune(a)) * 0.1
        chance_a -= rng.fortune_factor(debuff.effective_fortune(b)) * 0.1
        chance_a = min(0.95, max(0.05, chance_a))
        a_wins = rng.luck_roll(chance_a, a.get("fortune", 1000))

        if a_wins:
            dmg = max(1, int(a_max * constants.DUEL_ROUND_DAMAGE_RATIO))
            b_hp -= dmg
            logs.append(_round_text(a, b, dmg, b_hp, b_max, round_no))
            if b_hp <= 0:
                winner_id, loser_id = a_id, b_id
                break
        else:
            dmg = max(1, int(b_max * constants.DUEL_ROUND_DAMAGE_RATIO))
            a_hp -= dmg
            logs.append(_round_text(b, a, dmg, a_hp, a_max, round_no))
            if a_hp <= 0:
                winner_id, loser_id = b_id, a_id
                break

    if not winner_id:
        # 回合数耗尽（极端情况），按剩余气血判定胜负
        if a_hp >= b_hp:
            winner_id, loser_id = a_id, b_id
        else:
            winner_id, loser_id = b_id, a_id
        logs.append("😱 双方鏖战数百回合未分胜负，最终以气血多寡论生死！")

    # 结算：输家归西 + 损失灵石/修为；赢家获得输家损失的灵石
    return await _settle_duel(group_id, winner_id, loser_id, logs)


async def _settle_duel(group_id: int, winner_id: int, loser_id: int, logs: list[str]) -> dict:
    """生死台结算：输家归西并损失灵石/修为，赢家获得灵石"""
    winner = db.get_player(group_id, winner_id)
    loser = db.get_player(group_id, loser_id)
    if not winner or not loser:
        return {"ok": True, "text": "\n".join(logs)}

    w_name = winner.get("name") or str(winner_id)
    l_name = loser.get("name") or str(loser_id)

    # 输家损失灵石与修为
    coin_loss = int(loser.get("coin", 0) * constants.DUEL_LOSE_COIN_RATIO)
    progress_loss = int(loser.get("realm_progress", 0) * constants.DUEL_LOSE_PROGRESS_RATIO)
    new_coin = max(0, loser.get("coin", 0) - coin_loss)
    new_progress = max(0, loser.get("realm_progress", 0) - progress_loss)

    db.update_player(group_id, loser_id, {"coin": new_coin, "realm_progress": new_progress})
    db.update_player(group_id, winner_id, {"coin": winner.get("coin", 0) + coin_loss})

    # 输家归西
    combat.take_damage(group_id, loser_id, 999999)

    # 设置双方决斗冷却
    cache = get_cache()
    until = time.time() + constants.DUEL_COOLDOWN
    await cache.set(_cooldown_key(group_id, winner_id), until, expire=constants.DUEL_COOLDOWN)
    await cache.set(_cooldown_key(group_id, loser_id), until, expire=constants.DUEL_COOLDOWN)

    text = "\n".join(logs) + (
        f"\n💀 {l_name} 气血耗尽，当场陨落！生死台上，一决生死！\n"
        f"🏆 {w_name} 赢得生死台对决！\n"
        f"💰 {l_name} 损失 {coin_loss} 灵石、{progress_loss} 修为；{w_name} 获得 {coin_loss} 灵石"
    )
    return {"ok": True, "text": text, "winner": winner_id}

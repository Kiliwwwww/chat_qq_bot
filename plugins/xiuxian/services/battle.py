"""大乱斗系统。

玩家发送「报名大乱斗」报名，凑满 5 名玩家后自动开赛。
通过多轮战力对决（带气运加成），最终幸存 2 名玩家，各奖励 1000 灵石。
被淘汰的玩家气血耗尽，进入归西状态（60 秒后复活）。
"""

import random

from ..state import db
from . import combat, rng, stats

# 开赛所需人数
BATTLE_SIZE = 5

# 胜者奖励（灵石）
BATTLE_REWARD = 1000


def signup(group_id: int, user_id: int) -> dict:
    """报名大乱斗。满 5 人自动开赛。"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    if combat.is_dead(player):
        return {"ok": False, "text": f"你已归西，还需 {combat.dead_remain_seconds(player)} 秒复活，无法报名"}

    if db.is_battle_signed(group_id, user_id):
        return {"ok": False, "text": "你已经报名大乱斗了"}

    if not db.add_battle_signup(group_id, user_id):
        return {"ok": False, "text": "报名失败，请稍后再试"}

    signups = db.get_battle_signups(group_id)
    count = len(signups)
    if count < BATTLE_SIZE:
        return {"ok": True, "text": f"⚔️ 你已报名大乱斗！（{count}/{BATTLE_SIZE}），等待更多道友参加…"}

    # 满员开赛
    db.clear_battle_signups(group_id)
    return run_battle_royale(group_id, signups)


def _fight(player_a: dict, player_b: dict, group_id: int):
    """两名玩家对决，返回 (胜者, 败者)"""
    pa = stats.get_power(group_id, player_a)
    pb = stats.get_power(group_id, player_b)
    chance_a = pa / (pa + pb)
    chance_a += rng.fortune_factor(player_a.get("fortune", 1000)) * 0.1
    chance_a -= rng.fortune_factor(player_b.get("fortune", 1000)) * 0.1
    chance_a = min(0.95, max(0.05, chance_a))
    if rng.luck_roll(chance_a, player_a.get("fortune", 1000)):
        return player_a, player_b
    return player_b, player_a


def run_battle_royale(group_id: int, signups: list[dict]) -> dict:
    """模拟大乱斗，返回结果。"""
    fighters = []
    for s in signups:
        p = db.get_player(group_id, s["user_id"])
        if p:
            fighters.append(p)

    if len(fighters) < 2:
        return {"ok": True, "text": "大乱斗参加人数不足，本次取消"}

    logs = []
    round_no = 1
    while len(fighters) > 2:
        random.shuffle(fighters)
        round_log = []
        survivors = []
        i = 0
        while i < len(fighters) - 1:
            a = fighters[i]
            b = fighters[i + 1]
            winner, loser = _fight(a, b, group_id)
            survivors.append(winner)
            w_name = winner.get("name") or str(winner["user_id"])
            l_name = loser.get("name") or str(loser["user_id"])
            round_log.append(f"  · {w_name} 击败 {l_name}")
            # 淘汰者归西
            combat.take_damage(group_id, loser["user_id"], 999999)
            i += 2
        if len(fighters) % 2 == 1:
            survivors.append(fighters[-1])  # 轮空晋级
        logs.append(f"第 {round_no} 轮：\n" + "\n".join(round_log))
        fighters = survivors
        round_no += 1

    # 颁发奖励
    winners = fighters
    for w in winners:
        db.update_player(group_id, w["user_id"], {"coin": w.get("coin", 0) + BATTLE_REWARD})

    winner_names = "、".join(w.get("name") or str(w["user_id"]) for w in winners)
    text = (
        "⚔️ 【大乱斗开启】5 名修士混战，血流成河！\n"
        + "\n".join(logs)
        + f"\n🏆 最终幸存者：{winner_names}！\n"
        f"💰 各获得 {BATTLE_REWARD} 灵石奖励！"
    )
    return {"ok": True, "text": text, "winners": [w["user_id"] for w in winners]}


def format_signup_status(group_id: int) -> str:
    """查看当前大乱斗报名情况"""
    signups = db.get_battle_signups(group_id)
    if not signups:
        return f"⚔️ 大乱斗暂无人报名（{0}/{BATTLE_SIZE}），发送「报名大乱斗」参加！"
    names = []
    for s in signups:
        p = db.get_player(group_id, s["user_id"])
        names.append(p["name"] if p else str(s["user_id"]))
    return f"⚔️ 大乱斗报名（{len(signups)}/{BATTLE_SIZE}）：\n" + "\n".join(f"  · {n}" for n in names)

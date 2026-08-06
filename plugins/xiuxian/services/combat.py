"""战斗与血量系统。

- 血量：当前血量 cur_hp，上限为玩家的气血值（hp 属性）
- 归西：血量为 0 进入归西状态，一分钟后自动复活（恢复一半血量）
- PK：玩家间战力对决，赢家获胜，输家扣血，挑战者对被挑战者 5 分钟冷却
"""

import random
import time

from .. import constants
from ..state import config, db
from . import rng, stats

# 归西后复活所需时间（秒）
DEAD_REVIVE_SECONDS = 60

# PK 冷却时间（秒）
PK_COOLDOWN_SECONDS = 300

# PK 负向事件扣血比例
RISK_DAMAGE_RATIO = 0.15

# PK 胜负扣血比例
PK_DAMAGE_RATIO = 0.3


def get_max_hp(player: dict) -> int:
    """玩家气血上限"""
    return max(1, player.get("hp", 100))


def get_cur_hp(player: dict) -> int:
    """玩家当前血量。归西时为 0；未初始化（旧数据）按满血处理。"""
    cur = player.get("cur_hp", 0)
    if cur <= 0:
        if is_dead(player):
            return 0
        return get_max_hp(player)
    return min(cur, get_max_hp(player))


def is_dead(player: dict) -> bool:
    """是否处于归西状态"""
    return time.time() < player.get("dead_until", 0)


def dead_remain_seconds(player: dict) -> int:
    """归西剩余秒数"""
    remain = int(player.get("dead_until", 0) - time.time())
    return max(0, remain)


def try_revive(group_id: int, user_id: int) -> dict:
    """检查归西玩家是否到复活时间，到时自动复活（恢复一半血量）"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"revived": False}
    dead_until = player.get("dead_until", 0)
    if dead_until > 0 and time.time() >= dead_until:
        max_hp = get_max_hp(player)
        new_hp = max(1, int(max_hp * 0.5))
        db.update_player(group_id, user_id, {"cur_hp": new_hp, "dead_until": 0})
        return {"revived": True, "hp": new_hp, "max_hp": max_hp}
    return {"revived": False}


def take_damage(group_id: int, user_id: int, damage: int) -> dict:
    """扣除玩家血量，血量为 0 则进入归西状态。返回 {died, hp, max_hp}"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"died": False, "hp": 0, "max_hp": 1}
    max_hp = get_max_hp(player)
    cur = get_cur_hp(player)
    new_hp = max(0, cur - int(damage))
    died = False
    dead_until = player.get("dead_until", 0)
    if new_hp <= 0:
        new_hp = 0
        died = True
        dead_until = time.time() + DEAD_REVIVE_SECONDS
    db.update_player(group_id, user_id, {"cur_hp": new_hp, "dead_until": dead_until})
    return {"died": died, "hp": new_hp, "max_hp": max_hp}


def heal(group_id: int, user_id: int, amount: int) -> dict:
    """回复玩家血量，返回 {hp, max_hp}"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"hp": 0, "max_hp": 1}
    max_hp = get_max_hp(player)
    cur = get_cur_hp(player)
    new_hp = min(max_hp, cur + int(amount))
    db.update_player(group_id, user_id, {"cur_hp": new_hp})
    return {"hp": new_hp, "max_hp": max_hp}


def heal_full(group_id: int, user_id: int) -> dict:
    """将血量回满"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"hp": 0, "max_hp": 1}
    max_hp = get_max_hp(player)
    db.update_player(group_id, user_id, {"cur_hp": max_hp})
    return {"hp": max_hp, "max_hp": max_hp}


def revive_now(group_id: int, user_id: int) -> dict:
    """立即复活（涅槃丹）：清除归西状态并恢复一半血量"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色"}
    if not is_dead(player):
        return {"ok": False, "text": "你并未归西，无需复活"}
    max_hp = get_max_hp(player)
    new_hp = max(1, int(max_hp * 0.5))
    db.update_player(group_id, user_id, {"cur_hp": new_hp, "dead_until": 0})
    return {"ok": True, "text": f"🕊️ 涅槃重生！你已复活，气血恢复至 {new_hp}/{max_hp}"}


def apply_negative_damage(group_id: int, user_id: int, ratio: float = RISK_DAMAGE_RATIO) -> dict:
    """负向事件扣血（探索遇险/修炼遇险等）"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "died": False}
    max_hp = get_max_hp(player)
    damage = max(1, int(max_hp * ratio))
    result = take_damage(group_id, user_id, damage)
    if result["died"]:
        return {"ok": True, "died": True, "damage": damage, "text": f"你气血耗尽，魂归西天！{DEAD_REVIVE_SECONDS} 秒后复活"}
    return {"ok": True, "died": False, "damage": damage, "text": f"损失 {damage} 点气血（剩余 {result['hp']}/{result['max_hp']}）"}


def pk(group_id: int, attacker_id: int, target_id: int) -> dict:
    """玩家间 PK：按战力对决，赢家胜，输家扣血。挑战者对目标有 5 分钟冷却。"""
    attacker = db.get_player(group_id, attacker_id)
    target = db.get_player(group_id, target_id)
    if not attacker:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if not target:
        return {"ok": False, "text": "对方没有修仙角色"}
    if attacker_id == target_id:
        return {"ok": False, "text": "不能挑战自己"}

    if is_dead(attacker):
        return {"ok": False, "text": f"你已归西，还需 {dead_remain_seconds(attacker)} 秒复活"}
    if is_dead(target):
        return {"ok": False, "text": "对方正在归西状态，无法被挑战"}

    # 5 分钟冷却：挑战者对同一目标
    cooldown_until = db.get_pk_cooldown(group_id, attacker_id, target_id)
    if time.time() < cooldown_until:
        remain = int(cooldown_until - time.time())
        return {"ok": False, "text": f"你刚挑战过对方，还需 {remain} 秒才能再次挑战"}

    # 狂暴丹加成
    pk_boost = attacker.get("pk_boost", 0) or 0
    hp_cost = attacker.get("pk_hp_cost", 0) or 0

    att_power = stats.get_power(group_id, attacker)
    tgt_power = stats.get_power(group_id, target)
    att_power_boosted = int(att_power * (1 + pk_boost)) if pk_boost > 0 else att_power

    # 胜率：战力差距越大胜率越高（1/(1+ratio)，碾压时趋近 97%），再受双方气运影响
    ratio = tgt_power / max(1, att_power_boosted)
    win_chance = 1 / (1 + ratio)  # 对等 50%，两倍 33%，十倍 91%
    win_chance += rng.fortune_factor(attacker.get("fortune", 1000)) * 0.3
    win_chance -= rng.fortune_factor(target.get("fortune", 1000)) * 0.3
    win_chance = min(0.97, max(0.03, win_chance))

    won = rng.luck_roll(win_chance, attacker.get("fortune", 1000))

    # 设置冷却
    db.set_pk_cooldown(group_id, attacker_id, target_id, time.time() + PK_COOLDOWN_SECONDS)

    # 胜方不掉血；败方扣血
    if won:
        result = take_damage(group_id, target_id, int(get_max_hp(target) * PK_DAMAGE_RATIO))
        loser = target
        loser_id = target_id
    else:
        result = take_damage(group_id, attacker_id, int(get_max_hp(attacker) * PK_DAMAGE_RATIO))
        loser = attacker
        loser_id = attacker_id

    # 狂暴丹：PK 后额外扣除自身血量并消耗加成
    boost_text = ""
    if pk_boost > 0:
        extra = take_damage(group_id, attacker_id, hp_cost)
        boost_text = f"\n💥 狂暴丹反噬，额外损失 {hp_cost} 点气血！"
        db.update_player(group_id, attacker_id, {"pk_boost": 0, "pk_hp_cost": 0})

    att_hp = get_cur_hp(db.get_player(group_id, attacker_id))
    tgt_hp = get_cur_hp(db.get_player(group_id, target_id))
    loser_name = loser.get("name") or str(loser_id)

    # 戏剧性文案
    if won:
        outcome_text = random.choice([
            "你祭出杀招，剑光如虹，将对方彻底压制！",
            "你临阵顿悟，气势暴涨，一招定胜负！",
            "你运转玄功，天地之力加身，强势碾压对手！",
            "你身法如电，抓住对方破绽，一击制敌！",
            "你眉心绽放神芒，一道剑意横空，斩破长空！",
            "你召唤本命飞剑，万剑齐发，杀得对方毫无还手之力！",
            "你双掌一合，天地灵气疯狂涌入，一掌镇山河！",
            "你体内传来龙吟虎啸，气血冲霄，硬生生轰飞对手！",
            "你冷笑一声，袖袍一挥，一道罡气将对方轰出百丈！",
            "你踏空而起，一记翻天印当头压下，对方吐血倒飞！",
            "你指尖凝出一道雷光，天雷滚滚，炸得对方灰头土脸！",
            "你使出一招残影分身，真假难辨，本体一击致命！",
            "你体内旧伤尽愈，气息再攀高峰，越战越勇拿下胜利！",
            "你随手一招借力打力，四两拨千斤，对方自己撞上你的掌风！",
            "你长啸一声，身后浮现万丈法相，神威如狱，不战而屈人之兵！",
        ])
    else:
        outcome_text = random.choice([
            "对方突然临阵突破，气势暴涨，你被反杀！",
            "危难之际，对方身后似有高人暗中出手相助，你败下阵来！",
            "对方祭出隐藏杀招，你猝不及防，狼狈落败！",
            "你棋差一着，被对方抓住破绽，重重击倒在地！",
            "对方燃烧精血爆发潜能，你力有不逮，败下阵来！",
            "对方狂笑三声，周身魔焰滔天，你被压制得喘不过气！",
            "对方眼中金光一闪，竟有龙气护体，你的攻势尽数被化解！",
            "你脚下突现一道古老阵纹，道法被破，修为瞬间紊乱！",
            "对方凭空召唤出一尊金甲傀儡，三拳把你轰飞！",
            "你正要取胜，却听闻对方口中念念有词，引动天雷反噬于你！",
            "对方悄然使出摄魂之术，你心神失守，招式尽乱！",
            "你储物袋中异宝突然失灵，被对方抓住机会一击重创！",
            "对方化作一道残影欺身而近，一套连招打得你毫无还手之力！",
            "你体力透支，手脚发软，被对方一记重腿踢飞！",
            "对方临危不惧，祭出一枚保命符箓，反手将你轰退！",
            "眼看你即将得手，天空中突然降下一道惊雷劈中了你！",
            "你招式用老，被对方以柔克刚卸去力道，反手一掌正中胸口！",
            "对方竟是深藏不露，此刻才展露真正修为，你悔之晚矣！",
        ])

    if result["died"]:
        death_text = random.choice([
            f"💀 {loser_name} 气血耗尽，魂归西天！{DEAD_REVIVE_SECONDS} 秒后复活",
            f"💀 {loser_name} 被一击致命，当场陨落！{DEAD_REVIVE_SECONDS} 秒后复活",
            f"💀 {loser_name} 油尽灯枯，倒在血泊之中！{DEAD_REVIVE_SECONDS} 秒后复活",
            f"💀 {loser_name} 双目圆睁，不甘地轰然倒下！{DEAD_REVIVE_SECONDS} 秒后复活",
            f"💀 {loser_name} 被震碎护体罡气，化作一道流星坠入尘埃！{DEAD_REVIVE_SECONDS} 秒后复活",
            f"💀 {loser_name} 七窍溢血，肉身寸寸崩裂，当场陨灭！{DEAD_REVIVE_SECONDS} 秒后复活",
            f"💀 {loser_name} 神魂俱裂，惨叫着灰飞烟灭！{DEAD_REVIVE_SECONDS} 秒后复活",
            f"💀 {loser_name} 力竭倒地，最后一口气也散了！{DEAD_REVIVE_SECONDS} 秒后复活",
        ])
    else:
        death_text = random.choice([
            f"💔 {loser_name} 身受重伤，气血仅剩 {result['hp']}/{result['max_hp']}",
            f"💔 {loser_name} 被击得气血翻涌，连连后退，仅剩 {result['hp']}/{result['max_hp']} 气血",
            f"💔 {loser_name} 口中喷出一口鲜血，踉跄倒地，气血仅存 {result['hp']}/{result['max_hp']}",
            f"💔 {loser_name} 皮开肉绽，狼狈不堪，气血跌至 {result['hp']}/{result['max_hp']}",
        ])

    text = (
        f"⚔️ 【PK 对决】\n"
        f"📊 战力：你 {att_power_boosted}（原始 {att_power}） vs 对方 {tgt_power}，胜率 {int(win_chance * 100)}%\n"
        f"{outcome_text}\n"
        f"{death_text}"
    )
    if boost_text:
        text += boost_text
    text += f"\n📈 战后气血：你 {att_hp}，对方 {tgt_hp}"

    return {"ok": True, "text": text, "won": won}

"""弟子系统：高境界玩家可收低境界闭关玩家为弟子。

被收为弟子的玩家可触发「气运反制」：
天命觉醒 / 获得传承 / 反夺修为 / 偷学功法。
"""

import random
import time

from .. import constants
from ..state import config, db, get_cache
from . import debuff, rng, stats

_ESCAPE_COOLDOWN = 120  # 叛门尝试冷却（秒）


def capture(group_id: int, attacker_id: int, target_id: int) -> dict:
    """收低境界玩家为弟子。

    收徒需满足：
    - 境界高于对方
    - 战力高于对方
    - 成功率受战力差距与双方气运影响（气运高者更难被收，更容易收徒）
    """
    attacker = db.get_player(group_id, attacker_id)
    target = db.get_player(group_id, target_id)
    if not attacker:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if not target:
        return {"ok": False, "text": "对方没有修仙角色"}
    if attacker_id == target_id:
        return {"ok": False, "text": "不能收自己为弟子"}

    # 境界判定
    if attacker["realm"] <= target["realm"]:
        return {"ok": False, "text": "只有境界高于对方才能收徒"}

    # 战力对比
    attacker_power = stats.get_power(group_id, attacker)
    target_power = stats.get_power(group_id, target)
    if attacker_power <= target_power:
        return {"ok": False, "text": f"战力不足！你的战力 {attacker_power} 不高于对方 {target_power}，无法将其收为弟子"}

    # 对方必须正在闭关
    if not db.get_cultivation(group_id, target_id):
        return {"ok": False, "text": "对方没有在闭关，无法收徒"}

    # 对方已是弟子
    if db.get_furnace_by_target(group_id, target_id):
        return {"ok": False, "text": "对方已是他人弟子"}

    # 弟子数量上限（紫金道体可多收一个）
    furnace_limit = config.max_furnace
    if attacker.get("physique") == "zijin_luti":
        furnace_limit = config.max_furnace + 1
    if len(db.get_furnaces_by_owner(group_id, attacker_id)) >= furnace_limit:
        return {"ok": False, "text": f"弟子数量已达上限（{furnace_limit} 个）"}

    # 收徒成功率：基础随战力压制与境界差提升，双方气运影响成败
    power_ratio = target_power / max(1, attacker_power)  # 0~1，越接近1越难
    diff = attacker["realm"] - target["realm"]
    base = 0.7 - power_ratio * 0.25  # 0.45 ~ 0.7
    base += max(0, diff) * 0.04
    base += rng.fortune_factor(attacker.get("fortune", 1000)) * 0.5
    base -= rng.fortune_factor(target.get("fortune", 1000)) * 0.5
    success_chance = min(0.95, max(0.05, base))
    if not rng.luck_roll(success_chance, attacker.get("fortune", 1000)):
        return {"ok": False, "text": f"收徒失败！对方气运庇护，不愿拜入门下（成功率 {int(success_chance * 100)}%）"}

    if not db.add_furnace(group_id, attacker_id, target_id):
        return {"ok": False, "text": "收徒失败，请稍后再试"}

    # 打断对方修炼
    db.end_cultivation(group_id, target_id)
    return {
        "ok": True,
        "text": (
            f"⚡ 收徒成功！已将对方收为弟子，修炼效率提升！\n"
            f"📊 战力对比：你 {attacker_power} > 对方 {target_power}，成功率 {int(success_chance * 100)}%"
        ),
    }


def xiuxiu(group_id: int, user_id: int, index: int) -> dict:
    """为弟子传功，获得修为。

    传功收益 = 基础修为 + 弟子境界加成，带冷却时间。
    """
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    from . import combat
    if combat.is_dead(player):
        return {"ok": False, "text": f"你已归西，还需 {combat.dead_remain_seconds(player)} 秒复活，无法传功"}

    furnaces = db.get_furnaces_by_owner(group_id, user_id)
    if not furnaces:
        return {"ok": False, "text": "你还没有弟子，无法传功！先「收徒」一个闭关玩家吧"}

    if index < 1 or index > len(furnaces):
        return {"ok": False, "text": f"弟子编号不存在（1~{len(furnaces)}）"}

    # 冷却检查
    now = time.time()
    cooldown_until = player.get("xiuxiu_until", 0) or 0
    if now < cooldown_until:
        remain = int(cooldown_until - now)
        minutes = remain // 60
        seconds = remain % 60
        return {"ok": False, "text": f"传功消耗心神，还需 {minutes} 分 {seconds} 秒才能再次传功"}

    furnace = furnaces[index - 1]
    target = db.get_player(group_id, furnace["target_id"])
    target_realm = target["realm"] if target else 0

    # 传功收益：当前境界容量的百分比
    realm_index = player.get("realm", 0)
    capacity = constants.REALMS[realm_index]["capacity"]
    if capacity:
        gain = int(capacity * constants.XIUXIU_PROGRESS_RATE)
    else:
        # 飞升之境无容量上限，按当前修为百分比保底
        gain = max(100, int(player.get("realm_progress", 0) * constants.XIUXIU_PROGRESS_RATE))
    gain = max(1, gain)

    current = player.get("realm_progress", 0) + gain
    if capacity:
        current = min(current, capacity)
    db.update_player(group_id, user_id, {
        "realm_progress": current,
        "xiuxiu_until": now + config.xiuxiu_cooldown_minutes * 60,
    })

    target_name = target["name"] if target else str(furnace["target_id"])
    target_realm_name = constants.REALMS[target_realm]["name"] if target else "炼气"

    # 传功过度可能身体透支
    debuff_text = ""
    if rng.luck_roll(constants.DEBUFF_TRIGGER["xiuxiu_shenti_touzhi"], player.get("fortune", 1000)):
        d = debuff.add_debuff(group_id, user_id, "shenti_touzhi")
        debuff_text = f"\n😵 心神损耗过度，你感到【{d['name']}】，修炼将受到影响！"

    return {
        "ok": True,
        "text": (
            f"💞 【传功】你与弟子「{target_name}」（{target_realm_name}）心神相通，传授道法，气息暴涨！\n"
            f"✨ 获得修为 {gain}（当前境界容量的 {int(constants.XIUXIU_PROGRESS_RATE * 100)}%）（当前 {int(current)}）\n"
            f"⏳ 下次传功需等待 {config.xiuxiu_cooldown_minutes} 分钟"
            f"{debuff_text}"
        ),
    }


def list_furnaces(group_id: int, user_id: int) -> str:
    """查看自己拥有的弟子"""
    furnaces = db.get_furnaces_by_owner(group_id, user_id)
    if not furnaces:
        return "😴 你还没有弟子，收低境界的闭关玩家为弟子可以获得修炼加速"

    lines = ["🔥 【我的弟子】"]
    for i, f in enumerate(furnaces, start=1):
        target = db.get_player(group_id, f["target_id"])
        target_name = target["name"] if target else str(f["target_id"])
        lines.append(f"{i}. {target_name}（{constants.REALMS[target['realm']]['name']}）")
    lines.append("💡 每个弟子提供 10% 修炼加速（最多 3 个）")
    return "\n".join(lines)


def release_furnace(group_id: int, owner_id: int, index: int) -> dict:
    """逐出弟子"""
    furnaces = db.get_furnaces_by_owner(group_id, owner_id)
    if not furnaces:
        return {"ok": False, "text": "你没有弟子"}
    if index < 1 or index > len(furnaces):
        return {"ok": False, "text": f"弟子编号不存在（1~{len(furnaces)}）"}
    f = furnaces[index - 1]
    db.remove_furnace(group_id, owner_id, f["target_id"])
    target = db.get_player(group_id, f["target_id"])
    target_name = target["name"] if target else str(f["target_id"])
    return {"ok": True, "text": f"🕊️ 你已逐出弟子「{target_name}」，对方恢复了自由！"}


async def escape(group_id: int, user_id: int) -> dict:
    """被收为弟子的玩家尝试叛出师门（气运反制）"""
    furnace = db.get_furnace_by_target(group_id, user_id)
    if not furnace:
        return {"ok": False, "text": "你没有拜入任何师门"}

    # 冷却检查（Redis 缓存）
    cache = get_cache()
    key = f"{group_id}:escape_cd:{user_id}"
    last_attempt = await cache.get(key)
    if last_attempt and time.time() - float(last_attempt) < _ESCAPE_COOLDOWN:
        remain = int(_ESCAPE_COOLDOWN - (time.time() - float(last_attempt)))
        return {"ok": False, "text": f"叛门消耗心神，还需 {remain} 秒才能再次尝试"}

    player = db.get_player(group_id, user_id)
    fortune = player.get("fortune", 1000)

    # 叛门成功率：气运越高越容易
    success_chance = 0.35 + rng.fortune_factor(fortune)
    if player.get("physique") == "jiuyin_lt":
        success_chance += 0.10  # 九阴灵体反抗之力增强
    if player.get("physique") == "xuanyin_dinglu":
        success_chance -= 0.10  # 玄阴道体天生被束缚，叛门更困难
    success_chance = min(0.9, max(0.05, success_chance))

    if not rng.luck_roll(success_chance, fortune):
        await cache.set(key, time.time(), expire=_ESCAPE_COOLDOWN)
        return {"ok": False, "text": f"叛门失败！被强大的禁制压制，下次再试（{int(_ESCAPE_COOLDOWN / 60)} 分钟冷却）"}

    # 叛门成功，触发气运反制
    owner_id = furnace["owner_id"]
    db.remove_furnace(group_id, owner_id, user_id)

    anti_roll = rng.luck_roll(0.35, fortune)
    bonus_text = ""

    if anti_roll or player.get("physique") == "xuanyin_dinglu":
        # 玄阴道体叛门成功后必定触发天命觉醒
        reward_type = "awaken" if player.get("physique") == "xuanyin_dinglu" else random.choice(["awaken", "inherit", "steal", "retroactive"])
        if reward_type == "awaken":
            gain = int(fortune * 0.1)
            db.update_player(group_id, user_id, {"fortune": fortune + gain})
            bonus_text = f"\n🌟 天命觉醒！气运 +{gain}，从此逆天改命！"
        elif reward_type == "inherit":
            # 获得一本新功法
            from .player import pick_starter_gongfa
            gf = pick_starter_gongfa(player["spirit_root"])
            db.learn_gongfa(group_id, user_id, gf["id"])
            bonus_text = f"\n📜 上古传承！领悟功法【{gf['name']}】！"
        elif reward_type == "steal":
            # 偷学师父的一本功法
            owner_gongfas = db.get_gongfas(group_id, owner_id)
            if owner_gongfas:
                stolen = random.choice(owner_gongfas)
                info = constants.GONGFA_BY_ID.get(stolen["gongfa_id"], {})
                db.learn_gongfa(group_id, user_id, stolen["gongfa_id"])
                bonus_text = f"\n📜 偷学功法！习得【{info.get('name', stolen['gongfa_id'])}】！"
            else:
                bonus_text = "\n💡 反噬师父，却一无所获"
        elif reward_type == "retroactive":
            # 反夺师父的修为
            owner = db.get_player(group_id, owner_id)
            if owner:
                stolen_progress = int(owner.get("realm_progress", 0) * 0.1)
                db.update_player(group_id, user_id, {"realm_progress": player.get("realm_progress", 0) + stolen_progress})
                db.update_player(group_id, owner_id, {"realm_progress": max(0, owner.get("realm_progress", 0) - stolen_progress)})
                bonus_text = f"\n⚡ 反夺修为！从师父处夺走 {stolen_progress} 修为！"
    else:
        bonus_text = "\n📝 你脱离了师门，恢复了自由"

    await cache.set(key, time.time(), expire=_ESCAPE_COOLDOWN)
    return {"ok": True, "text": f"🕊️ 你成功叛出了师门！{bonus_text}"}

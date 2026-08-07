"""域外天魔入侵系统。

域外天魔大军降临全群，入侵期间所有玩家停止修炼/探索/炼丹/炼器等操作，
必须发送「迎击天魔」击退天魔大军。剿灭全部天魔或入侵时间耗尽时事件结束。
"""

import random
import time

from .. import constants
from ..state import config, db
from . import combat, rng, stats, world


def _event_active(group_id: int) -> bool:
    """世界事件是否为域外天魔入侵"""
    return world.get_current_event(group_id).get("name") == "域外天魔入侵"


def is_active(group_id: int) -> bool:
    """域外天魔入侵是否进行中"""
    if not _event_active(group_id):
        return False
    state = db.get_world_state(group_id)
    return state.get("invasion_max_hp", 0) > 0 and state.get("invasion_hp", 0) > 0


def is_running(group_id: int) -> bool:
    """入侵是否仍处于持续中（含天魔已被剿灭但事件未结算）"""
    return _event_active(group_id)


def force_start(group_id: int) -> str:
    """管理员手动开启域外天魔入侵，返回公告文本。"""
    if is_running(group_id):
        return "当前已有域外天魔入侵正在进行中，无法重复开启"
    if not db.execute_raw("SELECT user_id FROM players WHERE group_id = ?", (group_id,)):
        return "群内没有玩家，无法开启域外天魔入侵"

    now = time.time()
    end_time = now + constants.INVASION_LIFETIME_MINUTES * 60
    db.update_world_state(group_id, {
        "current_event": "yuwai_tianmo",
        "event_end_time": end_time,
        "secret_realm_end_time": 0,
    })
    db.log_world_event(group_id, "yuwai_tianmo", constants.WORLD_EVENTS["yuwai_tianmo"]["name"])
    return start_invasion(group_id)


def force_end(group_id: int) -> str:
    """管理员手动提前结束域外天魔入侵并按贡献结算，返回公告文本。"""
    if not is_running(group_id):
        return "当前没有进行中的域外天魔入侵"

    state = get_invasion_state(group_id)
    contribs = db.get_invasion_contributions(group_id)
    dealt = sum(c["total_damage"] for c in contribs) or 0
    cleared_ratio = min(1.0, dealt / max(1, state["max_hp"]))

    # 全部剿灭：正常发放全额奖励
    if cleared_ratio >= 1.0:
        reward_text = _grant_rewards(group_id, state["max_hp"])
        return f"🌄 【域外天魔入侵】天魔大军已被彻底剿灭！\n{reward_text}"

    # 提前结束：按已完成伤害比例发放奖励
    if not contribs:
        db.update_world_state(group_id, {"invasion_hp": 0, "invasion_max_hp": 0})
        db.clear_invasion_damage(group_id)
        db.update_world_state(group_id, {"current_event": "", "event_end_time": 0})
        return "🌄 【域外天魔入侵】已提前结束，无人迎击，无奖励结算"

    reward_text = _grant_rewards(group_id, state["max_hp"] * cleared_ratio)
    return (
        f"🌄 【域外天魔入侵】已被提前结束！\n"
        f"📊 天魔大军剩余 {int(state['hp'])}/{int(state['max_hp'])}，按已剿灭比例结算奖励\n"
        f"{reward_text}"
    )


def start_invasion(group_id: int) -> str:
    """触发域外天魔入侵：生成天魔大军，返回公告文本。"""
    avg_power = _average_power(group_id)
    max_hp = max(constants.INVASION_MIN_HP, int(avg_power * constants.INVASION_HP_FACTOR))
    db.update_world_state(group_id, {"invasion_hp": max_hp, "invasion_max_hp": max_hp})
    db.clear_invasion_damage(group_id)

    # 强制中断所有玩家的闭关，让全员必须迎击天魔
    for cult in db.get_all_cultivating(group_id):
        db.end_cultivation(group_id, cult["user_id"])

    return (
        f"🌑 【域外天魔入侵】\n"
        f"域外天魔大军降临仙域！全服修士停止一切修炼与探索！\n"
        f"👾 天魔大军气血：{int(max_hp)}\n"
        f"⚔️ 请立即发送「迎击天魔」共同迎敌！\n"
        f"⏳ 限时 {constants.INVASION_LIFETIME_MINUTES} 分钟，剿灭天魔或时间耗尽则结束！"
    )


def _average_power(group_id: int) -> int:
    """群内玩家平均战力"""
    rows = db.execute_raw("SELECT user_id FROM players WHERE group_id = ?", (group_id,))
    total = 0
    count = 0
    for r in rows:
        p = db.get_player(group_id, r["user_id"])
        if p:
            total += stats.get_power(group_id, p)
            count += 1
    return int(total / count) if count else 0


def get_invasion_state(group_id: int) -> dict:
    state = db.get_world_state(group_id)
    return {
        "hp": state.get("invasion_hp", 0),
        "max_hp": state.get("invasion_max_hp", 0),
    }


def attack_demon(group_id: int, user_id: int) -> dict:
    """玩家迎击天魔"""
    if not is_active(group_id):
        return {"ok": False, "text": "当前没有域外天魔入侵"}

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if combat.is_dead(player):
        return {"ok": False, "text": f"你已归西，还需 {combat.dead_remain_seconds(player)} 秒复活，无法迎击"}

    # 玩家伤害 = 战力 × 随机比例 × 气运加成
    from . import debuff
    power = stats.get_power(group_id, player)
    dmg_ratio = random.uniform(constants.INVASION_DMG_MIN, constants.INVASION_DMG_MAX)
    dmg = power * dmg_ratio * (1 + rng.fortune_factor(debuff.effective_fortune(player)))
    dmg = max(1, int(dmg))

    # 天魔反击：按玩家气血上限固定比例扣血
    counter = max(1, int(combat.get_max_hp(player) * constants.INVASION_COUNTER_RATIO))
    hit = combat.take_damage(group_id, user_id, counter)

    state = get_invasion_state(group_id)
    new_hp = state["hp"] - dmg
    db.add_invasion_damage(group_id, user_id, dmg)

    attack_text = random.choice([
        f"⚔️ 你祭出法宝，化作惊鸿斩向天魔大军，造成 {dmg} 伤害！",
        f"⚔️ 你灵力爆发，一掌轰出万千罡气，重创天魔，造成 {dmg} 伤害！",
        f"⚔️ 你剑意冲霄，劈开魔云斩杀魔卒，造成 {dmg} 伤害！",
        f"⚔️ 你身若游龙冲入魔阵，大开杀戒，造成 {dmg} 伤害！",
        f"⚔️ 你凝聚雷法轰落天雷，魔卒灰飞烟灭，造成 {dmg} 伤害！",
        f"⚔️ 你长啸一声，元神之剑斩向天魔头目，造成 {dmg} 伤害！",
    ])

    if hit["died"]:
        hit_text = random.choice([
            "💀 你被天魔围攻，气血耗尽，当场陨落！60 秒后复活",
            "💀 一只魔爪穿透你的护体罡气，你重伤倒下！60 秒后复活",
            "💀 魔潮汹涌，你力战不敌，魂归西天！60 秒后复活",
        ])
    else:
        hit_text = random.choice([
            f"🩸 天魔反扑，你被魔气冲击，损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）",
            f"🩸 一只天魔偷袭得手，你损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）",
        ])

    if new_hp <= 0:
        new_hp = 0
        db.update_world_state(group_id, {"invasion_hp": new_hp})
        reward_text = _grant_rewards(group_id, state["max_hp"])
        return {
            "ok": True,
            "text": f"{attack_text}\n💥 天魔大军被彻底剿灭！仙域重归太平！\n{hit_text}\n{reward_text}",
        }

    db.update_world_state(group_id, {"invasion_hp": new_hp})
    ratio = new_hp / max(1, state["max_hp"])
    if ratio > 0.75:
        condition = "天魔大军气势正盛，魔气遮天蔽日"
    elif ratio > 0.5:
        condition = "天魔大军遭到重创，攻势渐缓"
    elif ratio > 0.25:
        condition = "天魔大军溃不成军，败象已现"
    else:
        condition = "天魔大军苟延残喘，即将全军覆没"

    return {
        "ok": True,
        "text": f"{attack_text}\n👾 {condition}（{int(new_hp)}/{int(state['max_hp'])}）\n{hit_text}",
    }


def _grant_rewards(group_id: int, max_hp: float) -> str:
    """天魔被剿灭后按贡献发放奖励"""
    contribs = db.get_invasion_contributions(group_id)
    total_damage = sum(c["total_damage"] for c in contribs) or 1

    coin_pool = min(int(max_hp * constants.INVASION_SHARE_POOL_FACTOR), constants.INVASION_SHARE_POOL_CAP)
    progress_pool = int(max_hp * constants.INVASION_PROGRESS_REWARD)
    lines = ["🏆 【击退天魔】奖励结算："]

    for c in contribs:
        uid = c["user_id"]
        p = db.get_player(group_id, uid)
        if not p:
            continue
        share = c["total_damage"] / total_damage
        coins = constants.INVASION_REWARD_BASE + int(coin_pool * share)
        if p.get("physique") == "caiyuan_ti":
            coins = int(coins * 1.5)
        progress = int(progress_pool * share)
        db.update_player(group_id, uid, {
            "coin": p.get("coin", 0) + coins,
            "realm_progress": _add_progress_capped(group_id, p, progress),
        })
        name = p.get("name") or str(uid)
        lines.append(f"  · {name}：灵石 +{coins}，修为 +{progress}")

    if contribs:
        mvp = contribs[0]
        mp = db.get_player(group_id, mvp["user_id"])
        if mp:
            db.update_player(group_id, mvp["user_id"], {"coin": mp.get("coin", 0) + constants.INVASION_REWARD_MVP})
            lines.append(f"  🥇 除魔先锋：{mp['name']} 额外获得 {constants.INVASION_REWARD_MVP} 灵石！")

    db.update_world_state(group_id, {"invasion_hp": 0, "invasion_max_hp": 0})
    db.clear_invasion_damage(group_id)
    # 成功剿灭后立即结束入侵事件，世界恢复平静
    db.update_world_state(group_id, {"current_event": "", "event_end_time": 0})
    return "\n".join(lines)


def _add_progress_capped(group_id: int, player: dict, progress: int) -> float:
    realm_index = player.get("realm", 0)
    capacity = constants.REALMS[realm_index]["capacity"]
    current = player.get("realm_progress", 0) + progress
    if capacity:
        current = min(current, capacity)
    return current


def check_timeout(group_id: int) -> str | None:
    """检查入侵是否因时间耗尽而失败，返回公告文本。"""
    if not _event_active(group_id):
        return None
    state = db.get_world_state(group_id)
    if state.get("invasion_hp", 0) <= 0:
        return None  # 已成功剿灭
    event_end = state.get("event_end_time", 0)
    if time.time() >= event_end:
        db.update_world_state(group_id, {"invasion_hp": 0, "invasion_max_hp": 0})
        db.clear_invasion_damage(group_id)
        return (
            "🌫️ 【域外天魔入侵】"
            "时间耗尽，天魔大军卷土重来，仙域生灵涂炭！"
            "全服修士未能成功抵御，下次务必齐心协力！"
        )
    return None


def block_message(group_id: int) -> str:
    """域外天魔入侵期间的封禁提示文案（无入侵返回空串）"""
    if is_active(group_id):
        return (
            "🌑 域外天魔正在入侵！全服修士必须迎击天魔，"
            "暂时无法进行修炼/探索/炼丹/炼器等操作！发送「迎击天魔」参战"
        )
    return ""


def format_status(group_id: int) -> str:
    """查看天魔入侵状态"""
    if not _event_active(group_id):
        return "🌑 当前没有域外天魔入侵，仙域一片祥和"
    state = get_invasion_state(group_id)
    contribs = db.get_invasion_contributions(group_id)
    if not contribs:
        contrib_text = "  （暂无修士迎击）"
    else:
        contrib_text = "\n".join(
            f"  · {db.get_player(group_id, c['user_id']).get('name', str(c['user_id'])) if db.get_player(group_id, c['user_id']) else c['user_id']}：{int(c['total_damage'])} 伤害"
            for c in contribs[:5]
        )
    return (
        f"🌑 【域外天魔入侵】\n"
        f"👾 天魔大军气血：{int(state['hp'])}/{int(state['max_hp'])}\n"
        f"⚔️ 发送「迎击天魔」参战！\n"
        f"📊 除魔贡献：\n{contrib_text}"
    )

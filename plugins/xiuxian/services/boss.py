"""世界 Boss 系统。

Boss 随机刷新在群内，实力按群内最强玩家战力定（比最强玩家强一点）。
全群玩家可讨伐，Boss 死亡后按伤害贡献分配奖励，超时则逃脱。
"""

import random
import time

from .. import constants
from ..state import config, db
from . import combat, debuff, rng, stats, world


def get_average_power(group_id: int) -> int:
    """群内玩家平均战力"""
    players = db.execute_raw("SELECT user_id FROM players WHERE group_id = ?", (group_id,))
    total = 0
    count = 0
    for r in players:
        p = db.get_player(group_id, r["user_id"])
        if p:
            total += stats.get_power(group_id, p)
            count += 1
    return int(total / count) if count else 0


def get_active_boss(group_id: int) -> dict | None:
    """获取当前存活中的 Boss，过期则清除并返回 None"""
    boss = db.get_world_boss(group_id)
    if not boss:
        return None
    if time.time() >= boss["expire_time"]:
        db.clear_world_boss(group_id)
        return None
    return boss


def _do_spawn(group_id: int) -> str | None:
    """实际生成一只世界 Boss（不检查概率），返回公告文本。"""
    if get_active_boss(group_id):
        return None

    avg_power = get_average_power(group_id)
    if avg_power <= 0:
        return None  # 群里没有玩家，不刷新

    max_hp = max(constants.BOSS_MIN_MAX_HP, int(avg_power * constants.BOSS_MAX_HP_FACTOR))
    attack = max(50, int(avg_power * constants.BOSS_ATTACK_FACTOR))
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


def maybe_spawn(group_id: int) -> str | None:
    """按概率刷新世界 Boss（自动推送），成功返回公告文本。"""
    if random.random() >= constants.BOSS_SPAWN_CHANCE:
        return None
    return _do_spawn(group_id)


def force_spawn(group_id: int) -> str | None:
    """管理员手动开启 Boss 挑战（忽略概率，立即刷新）。"""
    return _do_spawn(group_id)


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

    # 玩家伤害 = 战力 × 随机比例 × 气运加成（灵气潮汐事件期间增伤）
    power = stats.get_power(group_id, player)
    dmg_ratio = random.uniform(constants.BOSS_DMG_MIN, constants.BOSS_DMG_MAX)
    dmg = power * dmg_ratio * (1 + rng.fortune_factor(debuff.effective_fortune(player)))
    # 星辉圣体：讨伐伤害+30%
    if player.get("physique") == "xinghui_st":
        dmg *= 1.3
    if world.get_current_event(group_id).get("name") == "灵气潮汐":
        dmg *= constants.BOSS_EVENT_DAMAGE_MULT
    dmg = max(1, int(dmg))

    # Boss 反击：每次按玩家自身气血上限固定掉 10%，不会一刀秒
    counter = max(1, int(combat.get_max_hp(player) * constants.BOSS_COUNTER_RATIO))
    hit = combat.take_damage(group_id, user_id, counter)

    # 扣 Boss 血并记录贡献
    db.add_boss_damage(group_id, user_id, dmg)
    new_hp = boss["hp"] - dmg

    # 戏剧性文案：攻击
    attack_text = random.choice([
        f"你凝聚法力，一掌轰出，对 {boss['name']} 造成 {dmg} 伤害！",
        f"你祭出法宝，化作流光砸在 {boss['name']} 身上，造成 {dmg} 伤害！",
        f"你剑意纵横，斩向 {boss['name']}，留下深深剑痕，造成 {dmg} 伤害！",
        f"你灵力爆发，拳势惊天，轰得 {boss['name']} 倒退数丈，造成 {dmg} 伤害！",
        f"你抓住 {boss['name']} 的破绽一记暴击，它发出惊天惨叫，受到 {dmg} 伤害！",
        f"你召唤漫天雷光劈落，{boss['name']} 被电得浑身焦黑，受到 {dmg} 伤害！",
        f"你以气御剑，飞剑穿胸而过，{boss['name']} 喷出一口黑血，受到 {dmg} 伤害！",
        f"你双目微阖，一道元神之剑斩向 {boss['name']} 识海，造成 {dmg} 伤害！",
    ])

    # 戏剧性文案：Boss 反击
    if hit["died"]:
        hit_text = random.choice([
            f"💀 你被 {boss['name']} 一击贯穿，当场陨落！60 秒后复活",
            f"💀 你力竭倒地，被 {boss['name']} 狂暴撕碎！60 秒后复活",
            f"💀 {boss['name']} 一声怒吼，音波将你震得神魂俱灭！60 秒后复活",
            f"💀 你躲闪不及，被 {boss['name']} 的致命一击轰成飞灰！60 秒后复活",
        ])
    else:
        hit_text = random.choice([
            f"你被 {boss['name']} 的利爪扫中，损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）",
            f"你躲闪不及，被 {boss['name']} 轰飞数丈，损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）",
            f"{boss['name']} 吐出一口毒雾，你中毒损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）",
            f"{boss['name']} 尾巴横扫，你格挡不及被抽中，损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）",
            f"你招架不及，被 {boss['name']} 的魔气冲撞，损失 {counter} 点气血（当前 {hit['hp']}/{hit['max_hp']}）",
        ])

    if new_hp <= 0:
        new_hp = 0
        db.update_world_boss(group_id, {"hp": new_hp, "last_hitter": user_id})
        kill_text = _grant_rewards(group_id, boss)
        return {
            "ok": True,
            "text": f"⚔️ {attack_text}\n💥 {boss['name']} 气血耗尽，轰然倒地！Boss 被击败！\n{hit_text}\n{kill_text}",
        }

    db.update_world_boss(group_id, {"hp": new_hp})
    return {
        "ok": True,
        "text": (
            f"⚔️ {attack_text}\n"
            f"💢 {_boss_condition_text(boss['max_hp'], new_hp)}（{int(new_hp)}/{int(boss['max_hp'])}）\n"
            f"{hit_text}"
        ),
    }


def _boss_condition_text(max_hp: float, hp: float) -> str:
    """根据 Boss 剩余血量生成状态描述（不含前缀）"""
    ratio = hp / max_hp if max_hp else 0
    if ratio >= 0.75:
        return random.choice([
            "Boss 气血充盈，仅受轻伤",
            "Boss 皮糙肉厚，这点伤对它来说不值一提",
            "Boss 狂怒嘶吼，战意正盛",
        ])
    if ratio >= 0.5:
        return random.choice([
            "Boss 气血有所损伤，气息微乱",
            "Boss 身上开始渗出黑血，攻势愈发疯狂",
            "Boss 怒吼连连，身上血痕累累",
        ])
    if ratio >= 0.25:
        return random.choice([
            "Boss 已现颓势，血痕累累，动作明显迟缓",
            "Boss 喘着粗气，眼中凶光闪烁，濒临暴怒",
            "Boss 节节败退，哀嚎不断",
        ])
    return random.choice([
        "Boss 重伤垂危，摇摇欲坠，即将崩溃！",
        "Boss 半边身体血肉模糊，已是强弩之末！",
        "Boss 发出最后嘶吼，最后一击即将到来！",
    ])


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
    """Boss 击杀后按输出比例发放奖励（灵石/修为/随机掉落），返回公告文本"""
    contribs = db.get_boss_contributions(group_id)
    total_damage = sum(c["total_damage"] for c in contribs) or 1
    last_hitter = db.get_world_boss(group_id)["last_hitter"] if db.get_world_boss(group_id) else 0

    coin_pool = min(int(boss["max_hp"] * constants.BOSS_SHARE_POOL_FACTOR), constants.BOSS_SHARE_POOL_CAP)
    progress_pool = int(boss["max_hp"] * constants.BOSS_PROGRESS_REWARD)
    lines = ["🏆 【讨伐成功】奖励结算："]

    for c in contribs:
        uid = c["user_id"]
        p = db.get_player(group_id, uid)
        if not p:
            continue
        share = c["total_damage"] / total_damage  # 0~1，输出占比
        coins = constants.BOSS_REWARD_BASE + int(coin_pool * share)
        if uid == last_hitter:
            coins += constants.BOSS_REWARD_LAST_HIT
        # 财源广进体：灵石奖励+50%
        if p.get("physique") == "caiyuan_ti":
            coins = int(coins * 1.5)
        progress = int(progress_pool * share)
        db.update_player(group_id, uid, {
            "coin": p.get("coin", 0) + coins,
            "realm_progress": _add_progress_capped(group_id, p, progress),
        })
        name = p["name"] or str(uid)
        drop_text = _roll_boss_drops(group_id, p, share)
        if drop_text:
            lines.append(f"  · {name}：灵石 +{coins}，修为 +{progress}，🎁掉落：{drop_text}")
        else:
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


def _roll_boss_drops(group_id: int, player: dict, share: float) -> str:
    """按输出占比概率随机掉落：丹药/灵兽/功法/突破材料，返回掉落文本（无掉落返回空串）"""
    fortune = player.get("fortune", 1000)
    uid = player["user_id"]
    got = []
    # 星辉圣体：掉落率提升
    drop_mult = 1.3 if player.get("physique") == "xinghui_st" else 1.0

    # 丹药
    pill_chance = min(0.9, constants.BOSS_DROP_PILL_CHANCE * (0.5 + share * 2) * drop_mult)
    if rng.luck_roll(pill_chance, fortune):
        pill = random.choice(constants.BOSS_DROP_PILLS)
        db.add_item(group_id, uid, pill, 1)
        got.append(f"丹药·{constants.ITEMS[pill]['name']}")

    # 灵兽
    pet_chance = min(0.6, constants.BOSS_DROP_PET_CHANCE * (0.5 + share * 2) * drop_mult)
    if rng.luck_roll(pet_chance, fortune):
        pet_type = rng.weighted_choice(constants.PET_TYPES)
        pet_id = random.randint(1, 99999999)
        db.add_pet(group_id, uid, pet_id, pet_type["id"], pet_type["name"])
        got.append(f"灵兽·{pet_type['name']}")

    # 功法
    gongfa_chance = min(0.6, constants.BOSS_DROP_GONGFA_CHANCE * (0.5 + share * 2) * drop_mult)
    if rng.luck_roll(gongfa_chance, fortune):
        gf = _pick_gongfa_for_player(group_id, player)
        if gf:
            db.learn_gongfa(group_id, uid, gf["id"])
            got.append(f"功法·{gf['name']}")

    # 突破材料（对应玩家下一境界所需的药材/丹药）
    btk_chance = min(0.8, constants.BOSS_DROP_BREAKTHROUGH_CHANCE * (0.5 + share * 2) * drop_mult)
    if rng.luck_roll(btk_chance, fortune):
        require = constants.BREAKTHROUGH_REQUIREMENTS.get(player.get("realm", 0))
        if require:
            herb_id, pill_id, _loc = require
            db.add_item(group_id, uid, herb_id, 1)
            db.add_item(group_id, uid, pill_id, 1)
            got.append(f"突破·{constants.ITEMS[herb_id]['name']}/{constants.ITEMS[pill_id]['name']}")

    return "、".join(got)


def _pick_gongfa_for_player(group_id: int, player: dict):
    """为玩家随机挑选一本可学习的功法（遵守灵根限制、未学、未超上限）"""
    root = player.get("spirit_root", "")
    if root == "空":
        pool = [g for gongfas in constants.GONGFAS.values() for g in gongfas]
    else:
        pool = constants.GONGFAS.get(root, [])

    owned = {g["gongfa_id"] for g in db.get_gongfas(group_id, player["user_id"])}
    available = [g for g in pool if g["id"] not in owned]
    if not available:
        return None
    return random.choice(available)


def _add_progress_capped(group_id: int, player: dict, progress: int) -> float:
    realm_index = player.get("realm", 0)
    capacity = constants.REALMS[realm_index]["capacity"]
    current = player.get("realm_progress", 0) + progress
    if capacity:
        current = min(current, capacity)
    return current

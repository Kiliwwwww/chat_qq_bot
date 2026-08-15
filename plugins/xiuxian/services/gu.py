"""蛊修系统。

不靠灵气修炼，核心是 空窍 + 蛊虫 + 真元。
- 资质（空窍天赋）：甲＞乙＞丙＞丁＞无，决定空窍容量/真元恢复/承载蛊虫数/修炼上限
- 境界：一转~九转，每转分初阶/中阶/高阶/巅峰；六转起为蛊仙（五转巅峰渡劫升仙）
- 核心行为：养蛊（喂食维持存活）、炼蛊（合炼新蛊/升级转数）、用蛊（耗真元催动）、运蛊/杀招（多蛊组合）
"""

import random
import time

from .. import constants
from ..state import config, db, get_cache
from . import rng


# ==================== 基础工具 ====================

def _aptitude_cfg(player: dict) -> dict:
    return constants.GU_APTITUDES.get(player.get("gu_aptitude", "无"), constants.GU_APTITUDES["无"])


def yuan_max(realm: int) -> int:
    return constants.GU_YUAN_BASE + realm * constants.GU_YUAN_STEP


def realm_display(player: dict) -> str:
    """境界展示：如 三转·中阶 / 六转·蛊仙·初阶"""
    realm = player.get("gu_realm", 0)
    sub = player.get("gu_sub_realm", 0)
    name = constants.GU_REALM_NAMES[realm]
    if player.get("gu_awaken"):
        name += "·蛊仙"
    elif realm >= 5:
        name += "·蛊仙"
    return f"{name}·{constants.GU_SUB_REALMS[sub]}"


def _tick_hunger(group_id: int, user_id: int, gus: list[dict]) -> list[dict]:
    """推进蛊虫饥饿度，饿死的蛊返回并删除"""
    now = time.time()
    dead = []
    for g in gus:
        elapsed_h = (now - g["last_fed"]) / 3600.0
        hunger = g["hunger"] + elapsed_h * constants.GU_HUNGER_PER_HOUR
        if hunger >= 100:
            dead.append(g)
        else:
            db.update_gu(group_id, user_id, g["id"], {"hunger": hunger, "last_fed": now})
    for g in dead:
        db.remove_gu(group_id, user_id, g["id"])
    return dead


def _pick_wild_gu(player: dict) -> dict | None:
    """随机一只可捕捉的野生蛊虫（不超过当前境界+1转；仙蛊全局唯一）"""
    realm = player.get("gu_realm", 0)
    uid = player["user_id"]
    max_tier = max(1, realm + 1)
    candidates = []
    for g in constants.GU_INSECTS:
        if g["tier"] > max_tier:
            continue
        if g.get("unique"):
            owner = db.get_unique_gu_owner(g["id"])
            if owner and owner != uid:
                continue
        candidates.append(g)
    if not candidates:
        return None
    return random.choice(candidates)


def _gain_cond(player: dict, amount: float) -> dict:
    """增加参悟进度，若满则提示可突破，返回更新后的玩家数据"""
    gu_cond = player.get("gu_cond", 0) + amount
    db.update_player(player["group_id"], player["user_id"], {"gu_cond": gu_cond})
    player["gu_cond"] = gu_cond
    return player


# ==================== 创建角色 ====================

def create_gu_character(group_id: int, user_id: int, name: str) -> dict:
    """创建蛊修角色（与灵修二选一）"""
    if db.get_player(group_id, user_id):
        return {"ok": False, "text": "你已经创建过角色了，不能同时走灵修与蛊修"}

    aptitude = rng.weighted_choice_dict(constants.GU_APTITUDE_WEIGHTS)
    ym = yuan_max(0)
    player_data = {
        "name": name, "realm": 0, "realm_progress": 0,
        "spirit_root": "", "spirit_quality": "丙",
        "fortune": constants.DEFAULT_FORTUNE,
        "physique": "", "talent": "gu",
        "attack": 10, "defense": 10, "hp": 100, "cur_hp": 100,
        "coin": 100, "alchemy_level": 1, "forge_level": 1,
        "cultivation_path": "gu",
        "gu_aptitude": aptitude, "gu_realm": 0, "gu_sub_realm": 0,
        "gu_yuan": ym, "gu_yuan_max": ym, "gu_cond": 0, "gu_awaken": 0,
    }
    if not db.create_player(group_id, user_id, player_data):
        return {"ok": False, "text": "创建角色失败，请稍后再试"}

    # 初始蛊虫
    db.add_gu(group_id, user_id, "daozu_gu")
    player_data["group_id"] = group_id
    player_data["user_id"] = user_id

    return {
        "ok": True,
        "text": (
            f"🐛 【蛊修入门】恭喜 {name or user_id} 踏上蛊修之路！\n"
            f"🧿 空窍资质：【{aptitude}】{constants.GU_APTITUDES[aptitude]['desc']}\n"
            f"🐛 初始蛊虫：刀足蛊×1\n"
            f"💡 发送「蛊修」查看面板，「寻蛊」捕捉蛊虫，「采气」修炼，「蛊养 1」喂蛊"
        ),
        "data": player_data,
    }


# ==================== 面板 ====================

def format_gu_status(group_id: int, user_id: int) -> str:
    """蛊修面板"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return "你不是蛊修，发送「我要修蛊」踏上蛊修之路"

    gus = db.get_gus(group_id, user_id)
    _tick_hunger(group_id, user_id, gus)
    gus = db.get_gus(group_id, user_id)

    aptitude = _aptitude_cfg(player)
    realm = player.get("gu_realm", 0)
    capacity = constants.GU_REALM_CAPACITY[realm]
    cond = player.get("gu_cond", 0)
    lines = [
        f"🐛 【蛊修面板】{player.get('name', '')}",
        f"🧿 资质：【{player.get('gu_aptitude', '无')}】（空窍可承载 {aptitude['capacity']} 只蛊）",
        f"🌀 境界：{realm_display(player)}",
        f"📈 参悟：{int(cond)}/{capacity}" + ("（可发送「蛊修突破」）" if cond >= capacity else ""),
        f"🔋 真元：{int(player.get('gu_yuan', 0))}/{int(player.get('gu_yuan_max', 100))}",
        f"🐛 蛊虫：{len(gus)}/{aptitude['capacity']} 只",
        f"💰 灵石：{player.get('coin', 0)}",
    ]
    if player.get("gu_awaken"):
        lines.append("☄️ 已渡劫成仙，真元化为【仙元】")
    if gus:
        lines.append("━━━")
        for i, g in enumerate(gus, start=1):
            info = constants.GU_INSECT_BY_ID.get(g["gu_id"], {})
            hunger_state = "饿死边缘" if g["hunger"] >= 70 else ("饥饿" if g["hunger"] >= 40 else "温饱")
            lines.append(
                f"  {i}. {info.get('name', g['gu_id'])}（{g['tier']}转·{info.get('category', '')}）"
                f" 饱食度 {100 - int(g['hunger'])} {hunger_state}"
            )
        lines.append("💡 指令：蛊养 <编号> / 用蛊 <编号> / 炼蛊 <编号们> / 运蛊")
    else:
        lines.append("🐛 你还没有蛊虫，发送「寻蛊」捕捉")
    return "\n".join(lines)


# ==================== 修炼 ====================

async def caigi(group_id: int, user_id: int, location: str = "洞府") -> dict:
    """采气：在特定地点吞吐天地元气，恢复真元并积累参悟进度（蛊修修炼方式）"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return {"ok": False, "text": "你不是蛊修，发送「我要修蛊」踏上蛊修之路"}

    # 地点校验
    if location not in constants.LOCATIONS:
        return {"ok": False, "text": f"未知采气地点，可选：{'、'.join(constants.LOCATIONS.keys())}"}

    # 常驻地图境界要求（蛊修转数：一转=0…九转=8，与灵修境界索引对应）
    realm_req = constants.LOCATION_REALM_REQUIRE.get(location, 0)
    if player.get("gu_realm", 0) < realm_req:
        required = constants.GU_REALM_NAMES[realm_req]
        return {"ok": False, "text": f"{location}需要达到【{required}】才能在此采气"}

    # 限时地图需对应世界事件开启
    from . import world
    if not world.is_location_open(group_id, location):
        event_name = world.location_open_event(location)
        if event_name:
            return {"ok": False, "text": f"{location}尚未开启，等待「{event_name}」事件出现吧"}
        return {"ok": False, "text": f"{location}尚未开启"}

    # 冷却
    cache = get_cache()
    cd_key = f"{group_id}:gu_caigi_cd:{user_id}"
    last = await cache.get(cd_key)
    if last and time.time() - float(last) < constants.GU_CAIQI_COOLDOWN:
        remain = int(constants.GU_CAIQI_COOLDOWN - (time.time() - float(last)))
        return {"ok": False, "text": f"采气消耗心神，还需 {remain} 秒"}

    aptitude = _aptitude_cfg(player)
    realm = player.get("gu_realm", 0)
    loc_mult = constants.LOCATIONS.get(location, {}).get("multiplier", 1.0)
    ymax = yuan_max(realm)
    cur = player.get("gu_yuan", 0)
    gain_yuan = int(ymax * 0.15 * aptitude["yuan_regen"] * loc_mult)
    new_yuan = min(ymax, cur + gain_yuan)

    # 修炼上限
    cap = aptitude["realm_cap"]
    at_cap = (realm >= cap and player.get("gu_sub_realm", 0) >= 3 and player.get("gu_cond", 0) >= constants.GU_REALM_CAPACITY[realm])

    gain_cond = 0
    if not at_cap:
        cap_val = constants.GU_REALM_CAPACITY[realm]
        gain_cond = int(max(10, cap_val * 0.12) * loc_mult)
        new_cond = player.get("gu_cond", 0) + gain_cond
    else:
        new_cond = player.get("gu_cond", 0)

    # 灵石收益（随境界转数与地点倍率提升，境界越高采气收获越多）
    gain_coins = int((30 + 45 * realm) * loc_mult)
    new_coin = player.get("coin", 0) + gain_coins

    db.update_player(group_id, user_id, {
        "gu_yuan": new_yuan, "gu_cond": new_cond, "coin": new_coin,
    })
    await cache.set(cd_key, time.time(), expire=constants.GU_CAIQI_COOLDOWN)

    text = (
        f"🌬️ 【采气·{location}】吞吐天地元气，真元 +{gain_yuan}（{int(new_yuan)}/{ymax}）\n"
        f"💰 灵石 +{gain_coins}"
    )
    if gain_cond > 0:
        text += f"📈 参悟 +{gain_cond}（{int(new_cond)}/{constants.GU_REALM_CAPACITY[realm]}）"
        if new_cond >= constants.GU_REALM_CAPACITY[realm]:
            text += "\n💡 修为已满，发送「蛊修突破」冲击更高境界！"
    else:
        text += "🛑 你已到资质上限，无法再精进（或需先「蛊修突破」）"

    # 采气时可能触发奇遇（与灵修共享奇遇池，奖励已适配蛊修）
    luck_mult = world.explore_luck_multiplier(group_id)
    from . import explore as explore_svc
    if rng.luck_roll(constants.ENCOUNTER_CHANCE * luck_mult, player.get("fortune", 1000)):
        text += explore_svc._apply_encounter(group_id, user_id, player.get("fortune", 1000), luck_mult)

    return {"ok": True, "text": text}


def gu_breakthrough(group_id: int, user_id: int, use_pill: bool = False) -> dict:
    """蛊修突破：小境界自动；大转需成功；五转巅峰渡劫升仙（可用破境丹提升成功率）"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return {"ok": False, "text": "你不是蛊修"}

    realm = player.get("gu_realm", 0)
    sub = player.get("gu_sub_realm", 0)
    capacity = constants.GU_REALM_CAPACITY[realm]
    cond = player.get("gu_cond", 0)
    if cond < capacity:
        need = int(capacity - cond)
        return {"ok": False, "text": f"参悟不足，还需 {need} 修为才能突破（发送「采气」修炼）"}

    fortune = player.get("fortune", 1000)

    # 破境丹：为突破提供额外成功率（五转巅峰渡劫同样有效）
    pill_bonus = 0.0
    if use_pill:
        if db.get_item_quantity(group_id, user_id, "pojing_dan") <= 0:
            return {"ok": False, "text": "你没有破境丹，先去商城购买或炼丹获取吧"}
        pill_bonus = constants.ITEMS["pojing_dan"]["effect"].get("breakthrough", 0.0)

    # 小境界突破（初阶→中阶→高阶→巅峰）
    if sub < 3:
        db.update_player(group_id, user_id, {"gu_sub_realm": sub + 1, "gu_cond": 0})
        return {"ok": True, "text": f"🎉 【突破】晋升至 {realm_display(db.get_player(group_id, user_id))}！"}

    # 五转巅峰 → 渡劫升仙
    if realm == 4:
        aptitude = _aptitude_cfg(player)
        if aptitude["realm_cap"] < 5:
            return {"ok": False, "text": "五转是凡人顶点！你【"+player.get("gu_aptitude","无")+"】资质，若无旷世机缘难以渡劫成仙"}
        base = {"甲": 0.6, "乙": 0.4, "丙": 0.2}.get(player.get("gu_aptitude", ""), 0.1)
        if use_pill:
            db.remove_item(group_id, user_id, "pojing_dan", 1)
        if rng.luck_roll(min(0.9, base + pill_bonus), fortune):
            ym = yuan_max(5)
            db.update_player(group_id, user_id, {"gu_realm": 5, "gu_sub_realm": 0, "gu_cond": 0, "gu_awaken": 1, "gu_yuan": ym, "gu_yuan_max": ym})
            return {"ok": True, "text": "☄️ 【渡劫成仙】你历经天劫洗礼，空窍化为仙窍，真元化为仙元！\n🌀 晋升【六转·蛊仙】！寿命大增，从此仙凡有别！"}
        # 渡劫失败
        db.update_player(group_id, user_id, {"gu_cond": int(cond * 0.3)})
        return {"ok": False, "text": "⚡ 【渡劫失败】天劫加身，参悟折损大半（剩余 30%）。重整旗鼓，再图仙缘！"}

    # 普通大转突破（一转~四转巅峰、以及蛊仙的大转）
    base = max(0.5, 0.85 - realm * 0.05)
    if use_pill:
        db.remove_item(group_id, user_id, "pojing_dan", 1)
    if rng.luck_roll(min(0.95, base + pill_bonus), fortune):
        ym = yuan_max(realm + 1)
        db.update_player(group_id, user_id, {"gu_realm": realm + 1, "gu_sub_realm": 0, "gu_cond": 0, "gu_yuan": ym, "gu_yuan_max": ym})
        return {"ok": True, "text": f"🎉 【突破】晋升至 {realm_display(db.get_player(group_id, user_id))}！真元上限提升！"}
    db.update_player(group_id, user_id, {"gu_cond": int(cond * 0.5)})
    return {"ok": False, "text": f"💥 【突破失败】真元紊乱，参悟损失一半（剩余 50%）"}


# ==================== 养蛊 ====================

def feed_gu(group_id: int, user_id: int, index: int) -> dict:
    """喂食蛊虫（消耗对应物品）"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return {"ok": False, "text": "你不是蛊修"}

    gus = db.get_gus(group_id, user_id)
    _tick_hunger(group_id, user_id, gus)
    gus = db.get_gus(group_id, user_id)
    if index < 1 or index > len(gus):
        return {"ok": False, "text": f"蛊虫编号不存在（1~{len(gus)}）"}

    gu = gus[index - 1]
    info = constants.GU_INSECT_BY_ID.get(gu["gu_id"], {})
    feed_type = info.get("feed", "血肉")
    item_id = constants.GU_FEED_ITEMS.get(feed_type)
    if not item_id:
        return {"ok": False, "text": f"【{info.get('name', gu['gu_id'])}】不知道该喂什么"}

    have = db.get_item_quantity(group_id, user_id, item_id)
    if have <= 0:
        item_name = constants.ITEMS.get(item_id, {}).get("name", item_id)
        return {"ok": False, "text": f"【{info.get('name', gu['gu_id'])}】以{feed_type}为食，需要 {item_name}（当前 {have}）"}

    db.remove_item(group_id, user_id, item_id, 1)
    new_hunger = max(0, gu["hunger"] - 50)
    db.update_gu(group_id, user_id, gu["id"], {"hunger": new_hunger, "last_fed": time.time()})

    item_name = constants.ITEMS.get(item_id, {}).get("name", item_id)
    return {"ok": True, "text": f"🍖 喂养【{info.get('name', gu['gu_id'])}】{item_name}×1，饱食度恢复至 {100 - int(new_hunger)}！"}


# ==================== 寻蛊 ====================

async def seek_gu(group_id: int, user_id: int) -> dict:
    """寻蛊：在野外捕捉一只蛊虫"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return {"ok": False, "text": "你不是蛊修"}

    cache = get_cache()
    cd_key = f"{group_id}:gu_seek_cd:{user_id}"
    last = await cache.get(cd_key)
    if last and time.time() - float(last) < constants.GU_SEEK_COOLDOWN:
        remain = int(constants.GU_SEEK_COOLDOWN - (time.time() - float(last)))
        return {"ok": False, "text": f"寻蛊需要休整，还需 {remain} 秒"}

    aptitude = _aptitude_cfg(player)
    count = db.get_insect_count(group_id, user_id)
    if count >= aptitude["capacity"]:
        return {"ok": False, "text": f"空窍已满（{count}/{aptitude['capacity']}），先炼蛊或放生再寻"}

    wild = _pick_wild_gu(player)
    if not wild:
        return {"ok": False, "text": "方圆百里无蛊可寻，稍后再试"}

    await cache.set(cd_key, time.time(), expire=constants.GU_SEEK_COOLDOWN)
    gid = db.add_gu(group_id, user_id, wild["id"])
    if not gid:
        return {"ok": False, "text": "捕捉失败，请稍后再试"}

    unique_note = "（仙蛊唯一，举世无双！）" if wild.get("unique") else ""
    return {"ok": True, "text": f"🐛 【寻蛊】捕捉到【{wild['name']}】×1（{wild['tier']}转·{wild['category']}）{unique_note}\n💬 {wild['desc']}"}


# ==================== 炼蛊 ====================

def refine_gu(group_id: int, user_id: int, indexes: list[int]) -> dict:
    """炼蛊：多只蛊合炼为更高转蛊，失败蛊虫损毁"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return {"ok": False, "text": "你不是蛊修"}

    gus = db.get_gus(group_id, user_id)
    _tick_hunger(group_id, user_id, gus)
    gus = db.get_gus(group_id, user_id)

    selected = []
    for i in indexes:
        if i < 1 or i > len(gus):
            return {"ok": False, "text": f"蛊虫编号 {i} 不存在（1~{len(gus)}）"}
        if i in selected:
            return {"ok": False, "text": "不能重复使用同一只蛊"}
        selected.append(i)

    if len(selected) < 2:
        return {"ok": False, "text": "炼蛊至少需要 2 只蛊虫，如：炼蛊 1 2 3"}

    chosen = [gus[i - 1] for i in selected]
    max_tier = max(g["tier"] for g in chosen)
    target_tier = min(9, max_tier + 1)

    # 费用
    cost = target_tier * 500
    if player.get("coin", 0) < cost:
        return {"ok": False, "text": f"炼蛊需要 {cost} 灵石（当前 {player.get('coin', 0)}）"}

    # 成功率
    base = max(0.2, 0.75 - target_tier * 0.05)
    success = rng.luck_roll(base, player.get("fortune", 1000))

    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - cost})
    for i in reversed(sorted(selected)):
        db.remove_gu(group_id, user_id, gus[i - 1]["id"])

    if not success:
        return {"ok": True, "text": f"💥 【炼蛊失败】道痕破碎，投入的 {len(selected)} 只蛊虫尽数损毁！"}

    # 生成新蛊：随机一只与目标转数匹配的蛊
    candidates = [g for g in constants.GU_INSECTS if g["tier"] == target_tier]
    if not candidates:
        return {"ok": True, "text": "炼蛊成功，但世上已无更高转蛊可炼"}
    new_gu = random.choice(candidates)
    if new_gu.get("unique"):
        owner = db.get_unique_gu_owner(new_gu["id"])
        if owner and owner != user_id:
            new_gu = random.choice([g for g in candidates if not g.get("unique")] or candidates)
    db.add_gu(group_id, user_id, new_gu["id"])

    return {"ok": True, "text": f"🔥 【炼蛊成功】{len(selected)} 只蛊虫合而为一，炼得【{new_gu['name']}】（{target_tier}转·{new_gu['category']}）！\n💬 {new_gu['desc']}"}


# ==================== 用蛊 / 运蛊 / 杀招 ====================

def use_gu(group_id: int, user_id: int, index: int) -> dict:
    """用蛊：消耗真元催动蛊虫，触发随机效果"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return {"ok": False, "text": "你不是蛊修"}

    gus = db.get_gus(group_id, user_id)
    _tick_hunger(group_id, user_id, gus)
    gus = db.get_gus(group_id, user_id)
    if index < 1 or index > len(gus):
        return {"ok": False, "text": f"蛊虫编号不存在（1~{len(gus)}）"}

    gu = gus[index - 1]
    info = constants.GU_INSECT_BY_ID.get(gu["gu_id"], {})

    cost = max(5, int(player.get("gu_yuan_max", 100) * 0.2))
    if player.get("gu_yuan", 0) < cost:
        return {"ok": False, "text": f"真元不足（需要 {cost}），先发送「采气」补充"}

    db.update_player(group_id, user_id, {"gu_yuan": player.get("gu_yuan", 0) - cost})

    # 随机效果
    roll = random.random()
    text = f"🐛 【用蛊·{info.get('name', gu['gu_id'])}】催动蛊虫"
    if roll < 0.35:
        coins = random.randint(50, 300) * max(1, gu["tier"])
        db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + coins})
        text += f"，收获满满！💰 灵石 +{coins}！"
    elif roll < 0.65:
        gain = random.randint(20, 80) * max(1, gu["tier"])
        realm = player.get("gu_realm", 0)
        cap = constants.GU_REALM_CAPACITY[realm]
        new_cond = min(cap, player.get("gu_cond", 0) + gain)
        db.update_player(group_id, user_id, {"gu_cond": new_cond})
        text += f"，感悟道韵！📈 参悟 +{gain}（{int(new_cond)}/{cap}）"
    elif roll < 0.85:
        item = random.choice(["yaodan", "lingquan", "lingcao", "xuantie"])
        db.add_item(group_id, user_id, item, 1)
        item_name = constants.ITEMS.get(item, {}).get("name", item)
        text += f"，搜刮到战利品！🎁 获得 {item_name}×1！"
    else:
        lost = random.randint(30, 120)
        db.update_player(group_id, user_id, {"coin": max(0, player.get("coin", 0) - lost)})
        text += f"，却被蛊反噬！💸 丢失 {lost} 灵石！"
    return {"ok": True, "text": text}


def _owned_category_counts(gus: list[dict]) -> dict:
    counts = {}
    for g in gus:
        info = constants.GU_INSECT_BY_ID.get(g["gu_id"], {})
        cat = info.get("category", "aux")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def list_kills(group_id: int, user_id: int) -> str:
    """运蛊：展示可用的杀招搭配"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return "你不是蛊修"

    gus = db.get_gus(group_id, user_id)
    _tick_hunger(group_id, user_id, gus)
    counts = _owned_category_counts(db.get_gus(group_id, user_id))

    lines = ["⚔️ 【运蛊·杀招】"]
    for k in constants.GU_KILLS:
        ok = all(counts.get(cat, 0) >= n for cat, n in k["req"].items())
        mark = "✅" if ok else "🔒"
        req_text = "、".join(f"{cat}{n}" for cat, n in k["req"].items())
        lines.append(f"  {mark} {k['name']}（需 {req_text}，威力×{k['power']}）")
        if ok:
            lines.append(f"      💬 {k['desc']} → 发送「杀招 {k['id']}」")
    lines.append("💡 先用「寻蛊」收集足够类别的蛊虫")
    return "\n".join(lines)


def use_kill(group_id: int, user_id: int, kill_id: str) -> dict:
    """释放杀招：多蛊协同，威力远胜单蛊"""
    player = db.get_player(group_id, user_id)
    if not player or player.get("cultivation_path") != "gu":
        return {"ok": False, "text": "你不是蛊修"}

    kill = constants.GU_KILL_BY_ID.get(kill_id)
    if not kill:
        names = "、".join(k["id"] for k in constants.GU_KILLS)
        return {"ok": False, "text": f"没有该杀招，可用：{names}"}

    gus = db.get_gus(group_id, user_id)
    _tick_hunger(group_id, user_id, gus)
    counts = _owned_category_counts(db.get_gus(group_id, user_id))
    if not all(counts.get(cat, 0) >= n for cat, n in kill["req"].items()):
        req_text = "、".join(f"{cat}{n}" for cat, n in kill["req"].items())
        return {"ok": False, "text": f"蛊虫搭配不足，需要 {req_text}（发送「运蛊」查看）"}

    cost = int(player.get("gu_yuan_max", 100) * 0.4)
    if player.get("gu_yuan", 0) < cost:
        return {"ok": False, "text": f"真元不足（需要 {cost}），先发送「采气」补充"}

    db.update_player(group_id, user_id, {"gu_yuan": player.get("gu_yuan", 0) - cost})

    # 杀招效果
    power = kill["power"]
    coins = int(random.randint(200, 800) * power)
    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + coins})
    gain = int(random.randint(50, 150) * power)
    realm = player.get("gu_realm", 0)
    cap = constants.GU_REALM_CAPACITY[realm]
    new_cond = min(cap, player.get("gu_cond", 0) + gain)
    db.update_player(group_id, user_id, {"gu_cond": new_cond})

    return {
        "ok": True,
        "text": (
            f"⚔️ 【杀招·{kill['name']}】{kill['desc']}！\n"
            f"💰 灵石 +{coins}，📈 参悟 +{gain}（{int(new_cond)}/{cap}）"
        ),
    }


# ==================== 蛊修战力 ====================

def gu_power(group_id: int, user_id: int, player: dict) -> int:
    """蛊修战力：境界基础 + 蛊虫叠加（仙蛊翻倍，蛊仙整体提升）"""
    gus = db.get_gus(group_id, user_id)
    _tick_hunger(group_id, user_id, gus)
    realm = player.get("gu_realm", 0)
    sub = player.get("gu_sub_realm", 0)
    power = constants.GU_POWER_BASE + realm * constants.GU_POWER_REALM + sub * constants.GU_POWER_SUB
    for g in db.get_gus(group_id, user_id):
        mult = constants.GU_POWER_UNIQUE_MULT if g.get("unique_flag") else 1
        power += g["tier"] * constants.GU_POWER_INSECT * mult
    if player.get("gu_awaken"):
        power = int(power * constants.GU_FAIRY_MULT)
    return max(1, power)


def is_gu_player(player: dict) -> bool:
    return bool(player) and player.get("cultivation_path") == "gu"

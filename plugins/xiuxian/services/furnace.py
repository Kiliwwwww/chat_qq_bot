"""炉鼎系统：高境界玩家可抓捕低境界闭关玩家作为炉鼎。

被俘玩家可触发「气运反制」：
天命觉醒 / 获得传承 / 反夺修为 / 偷学功法。
"""

import random
import time

from .. import constants
from ..state import config, db, get_cache
from . import rng

_ESCAPE_COOLDOWN = 600  # 挣脱尝试冷却（秒）


def capture(group_id: int, attacker_id: int, target_id: int) -> dict:
    """抓捕低境界玩家作为炉鼎"""
    attacker = db.get_player(group_id, attacker_id)
    target = db.get_player(group_id, target_id)
    if not attacker:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if not target:
        return {"ok": False, "text": "对方没有修仙角色"}
    if attacker_id == target_id:
        return {"ok": False, "text": "不能抓捕自己"}

    # 境界判定
    if attacker["realm"] <= target["realm"]:
        return {"ok": False, "text": "只有境界高于对方才能抓捕炉鼎"}

    # 对方必须正在闭关
    if not db.get_cultivation(group_id, target_id):
        return {"ok": False, "text": "对方没有在闭关，无法抓捕"}

    # 对方已是炉鼎
    if db.get_furnace_by_target(group_id, target_id):
        return {"ok": False, "text": "对方已是他人炉鼎"}

    # 炉鼎数量上限（紫金炉体可多抓一个）
    furnace_limit = config.max_furnace
    if attacker.get("physique") == "zijin_luti":
        furnace_limit = config.max_furnace + 1
    if len(db.get_furnaces_by_owner(group_id, attacker_id)) >= furnace_limit:
        return {"ok": False, "text": f"炉鼎数量已达上限（{furnace_limit} 个）"}

    # 抓捕成功率：境界差越大越容易
    diff = attacker["realm"] - target["realm"]
    success_chance = 0.5 + diff * 0.1
    if not rng.luck_roll(success_chance, attacker.get("fortune", 1000)):
        return {"ok": False, "text": "抓捕失败！对方奋力反抗，逃脱了你的掌控"}

    if not db.add_furnace(group_id, attacker_id, target_id):
        return {"ok": False, "text": "抓捕失败，请稍后再试"}

    # 打断对方修炼
    db.end_cultivation(group_id, target_id)
    return {"ok": True, "text": f"⚡ 抓捕成功！已将对方收为炉鼎，修炼效率提升！"}


def list_furnaces(group_id: int, user_id: int) -> str:
    """查看自己拥有的炉鼎"""
    furnaces = db.get_furnaces_by_owner(group_id, user_id)
    if not furnaces:
        return "😴 你还没有炉鼎，抓捕低境界的闭关玩家可以获得修炼加速"

    lines = ["🔥 【我的炉鼎】"]
    for i, f in enumerate(furnaces, start=1):
        target = db.get_player(group_id, f["target_id"])
        target_name = target["name"] if target else str(f["target_id"])
        lines.append(f"{i}. {target_name}（{constants.REALMS[target['realm']]['name']}）")
    lines.append("💡 每个炉鼎提供 10% 修炼加速（最多 3 个）")
    return "\n".join(lines)


def release_furnace(group_id: int, owner_id: int, index: int) -> dict:
    """释放炉鼎"""
    furnaces = db.get_furnaces_by_owner(group_id, owner_id)
    if not furnaces:
        return {"ok": False, "text": "你没有炉鼎"}
    if index < 1 or index > len(furnaces):
        return {"ok": False, "text": "炉鼎编号不存在"}
    f = furnaces[index - 1]
    db.remove_furnace(group_id, owner_id, f["target_id"])
    return {"ok": True, "text": f"你已释放炉鼎（编号 {index}）"}


async def escape(group_id: int, user_id: int) -> dict:
    """被俘玩家尝试挣脱（气运反制）"""
    furnace = db.get_furnace_by_target(group_id, user_id)
    if not furnace:
        return {"ok": False, "text": "你没有被抓捕为炉鼎"}

    # 冷却检查（Redis 缓存）
    cache = get_cache()
    key = f"{group_id}:escape_cd:{user_id}"
    last_attempt = await cache.get(key)
    if last_attempt and time.time() - float(last_attempt) < _ESCAPE_COOLDOWN:
        remain = int(_ESCAPE_COOLDOWN - (time.time() - float(last_attempt)))
        return {"ok": False, "text": f"挣脱消耗心神，还需 {remain} 秒才能再次尝试"}

    player = db.get_player(group_id, user_id)
    fortune = player.get("fortune", 1000)

    # 挣脱成功率：气运越高越容易
    success_chance = 0.35 + rng.fortune_factor(fortune)
    if player.get("physique") == "jiuyin_lt":
        success_chance += 0.10  # 九阴灵体反抗之力增强
    if player.get("physique") == "xuanyin_dinglu":
        success_chance -= 0.10  # 玄阴鼎炉天生被困，挣脱更困难
    success_chance = min(0.9, max(0.05, success_chance))

    if not rng.luck_roll(success_chance, fortune):
        await cache.set(key, time.time(), expire=_ESCAPE_COOLDOWN)
        return {"ok": False, "text": "挣脱失败！被强大的禁制压制，下次再试（10 分钟冷却）"}

    # 挣脱成功，触发气运反制
    owner_id = furnace["owner_id"]
    db.remove_furnace(group_id, owner_id, user_id)

    anti_roll = rng.luck_roll(0.35, fortune)
    bonus_text = ""

    if anti_roll or player.get("physique") == "xuanyin_dinglu":
        # 玄阴鼎炉挣脱成功后必定触发天命觉醒
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
            # 偷学主人的一本功法
            owner_gongfas = db.get_gongfas(group_id, owner_id)
            if owner_gongfas:
                stolen = random.choice(owner_gongfas)
                info = constants.GONGFA_BY_ID.get(stolen["gongfa_id"], {})
                db.learn_gongfa(group_id, user_id, stolen["gongfa_id"])
                bonus_text = f"\n📜 偷学功法！习得【{info.get('name', stolen['gongfa_id'])}】！"
            else:
                bonus_text = "\n💡 反噬宿主，却一无所获"
        elif reward_type == "retroactive":
            # 反夺主人的修为
            owner = db.get_player(group_id, owner_id)
            if owner:
                stolen_progress = int(owner.get("realm_progress", 0) * 0.1)
                db.update_player(group_id, user_id, {"realm_progress": player.get("realm_progress", 0) + stolen_progress})
                db.update_player(group_id, owner_id, {"realm_progress": max(0, owner.get("realm_progress", 0) - stolen_progress)})
                bonus_text = f"\n⚡ 反夺修为！从主人处夺走 {stolen_progress} 修为！"
    else:
        bonus_text = "\n📝 你挣脱了束缚，恢复了自由"

    await cache.set(key, time.time(), expire=_ESCAPE_COOLDOWN)
    return {"ok": True, "text": f"🕊️ 你成功挣脱了炉鼎束缚！{bonus_text}"}

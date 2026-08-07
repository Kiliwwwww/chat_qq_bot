"""境界突破系统。"""

import time

from .. import constants
from ..state import config, db
from . import debuff, rng, world

# 品质对突破成功率的加成
_QUALITY_BREAKTHROUGH_BONUS = {
    "废品": 0.00, "下品": 0.02, "中品": 0.05, "上品": 0.08, "极品": 0.12, "仙品": 0.15,
}


def attempt_breakthrough(group_id: int, user_id: int, use_pill: bool = False) -> dict:
    """尝试突破境界。

    use_pill: 是否使用破境丹
    """
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    realm_index = player.get("realm", 0)
    if realm_index >= len(constants.REALMS) - 1:
        return {"ok": False, "text": "你已臻至飞升之境，站在了修仙世界的顶点！"}

    # 瓶颈冷却
    bottleneck_until = player.get("bottleneck_until", 0)
    if time.time() < bottleneck_until:
        remain = int((bottleneck_until - time.time()) / 60)
        return {"ok": False, "text": f"你正处于突破瓶颈中，还需 {remain} 分钟才能再次尝试"}

    realm_cfg = constants.REALMS[realm_index]
    capacity = realm_cfg["capacity"]
    progress = player.get("realm_progress", 0)
    if progress < capacity:
        return {"ok": False, "text": f"修为不足，突破{constants.REALMS[realm_index + 1]['name']}需要 {int(capacity)} 修为（当前 {int(progress)}）"}

    # 突破大境界所需药材与丹药（灵药谷刷取或突破商人购买）
    require = constants.BREAKTHROUGH_REQUIREMENTS.get(realm_index)
    if require:
        herb_id, pill_id, location = require
        herb_name = constants.ITEMS.get(herb_id, {}).get("name", herb_id)
        pill_name = constants.ITEMS.get(pill_id, {}).get("name", pill_id)
        herb_have = db.get_item_quantity(group_id, user_id, herb_id)
        pill_have = db.get_item_quantity(group_id, user_id, pill_id)
        if herb_have <= 0 or pill_have <= 0:
            return {
                "ok": False,
                "text": (
                    f"突破需要【{herb_name}】和【{pill_name}】！（当前 药材{herb_have}/1、丹药{pill_have}/1）\n"
                    f"💡 可在「{location}」等地图探索获得，也可等「突破商人」现身坊市购买"
                ),
            }
        # 消耗材料
        db.remove_item(group_id, user_id, herb_id, 1)
        db.remove_item(group_id, user_id, pill_id, 1)

    # 计算成功率
    base = realm_cfg["breakthrough_base"]
    bonus = 0.0
    bonus += _QUALITY_BREAKTHROUGH_BONUS.get(player.get("spirit_quality", ""), 0.0)
    bonus += world.breakthrough_bonus(group_id)
    bonus += rng.fortune_factor(debuff.effective_fortune(player))
    # 造化圣体：突破成功率+10%
    if player.get("physique") == "zaohua_st":
        bonus += 0.10
    # 破境丹
    if use_pill:
        if db.get_item_quantity(group_id, user_id, "pojing_dan") <= 0:
            return {"ok": False, "text": "你没有破境丹，先去炼丹或坊市获取吧"}
        bonus += constants.ITEMS["pojing_dan"]["effect"]["breakthrough"]
        db.remove_item(group_id, user_id, "pojing_dan", 1)

    success_rate = min(0.95, max(0.05, base + bonus))
    success = rng.luck_roll(success_rate, debuff.effective_fortune(player))

    if success:
        new_realm = realm_index + 1
        # 境界提升，基础属性成长
        new_attack = int(player.get("attack", 10) * 1.15)
        new_defense = int(player.get("defense", 10) * 1.15)
        new_hp = int(player.get("hp", 100) * 1.15)
        leftover = progress - capacity
        db.update_player(group_id, user_id, {
            "realm": new_realm,
            "realm_progress": leftover,
            "attack": new_attack,
            "defense": new_defense,
            "hp": new_hp,
        })
        result = {
            "ok": True,
            "success": True,
            "old_realm": constants.REALMS[realm_index]["name"],
            "new_realm": constants.REALMS[new_realm]["name"],
            "rate": round(success_rate * 100, 1),
            "text": f"🎉 恭喜！你成功突破至【{constants.REALMS[new_realm]['name']}】境界！",
        }
        # 废材流主角高气运，突破时可能触发逆袭
        if player.get("talent") == "trash" and rng.luck_roll(0.2, player.get("fortune", 1000)):
            bonus_fortune = int(player.get("fortune", 10000) * 0.05)
            db.update_player(group_id, user_id, {"fortune": player.get("fortune", 10000) + bonus_fortune})
            result["text"] += f"\n🌟 废柴逆袭，天道共鸣！气运+{bonus_fortune}！"
        return result
    else:
        lost = int(progress * config.breakthrough_fail_penalty)
        new_progress = max(0, progress - lost)
        bottleneck_until = time.time() + constants.BOTTLENECK_MINUTES * 60
        db.update_player(group_id, user_id, {
            "realm_progress": new_progress,
            "bottleneck_until": bottleneck_until,
        })
        # 突破失败可能霉运缠身
        daomei_text = ""
        if rng.luck_roll(constants.DEBUFF_TRIGGER["breakthrough_fail_daomei"], player.get("fortune", 1000)):
            d = debuff.add_debuff(group_id, user_id, "daomei")
            daomei_text = f"\n😵 突破失败让你霉运缠身，气运大跌！"
        return {
            "ok": True,
            "success": False,
            "rate": round(success_rate * 100, 1),
            "text": f"💥 突破失败！损失 {lost} 修为，陷入瓶颈（{constants.BOTTLENECK_MINUTES} 分钟内无法再次突破）。"
                    f"\n💡 可服用「破境丹」提高成功率"
                    f"{daomei_text}",
        }

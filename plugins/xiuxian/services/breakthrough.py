"""境界突破系统。"""

import time

from .. import constants
from ..state import config, db
from . import rng, world

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

    # 计算成功率
    base = realm_cfg["breakthrough_base"]
    bonus = 0.0
    bonus += _QUALITY_BREAKTHROUGH_BONUS.get(player.get("spirit_quality", ""), 0.0)
    bonus += world.breakthrough_bonus(group_id)
    bonus += rng.fortune_factor(player.get("fortune", 1000))
    # 破境丹
    if use_pill:
        if db.get_item_quantity(group_id, user_id, "pojing_dan") <= 0:
            return {"ok": False, "text": "你没有破境丹，先去炼丹或坊市获取吧"}
        bonus += constants.ITEMS["pojing_dan"]["effect"]["breakthrough"]
        db.remove_item(group_id, user_id, "pojing_dan", 1)

    success_rate = min(0.95, max(0.05, base + bonus))
    success = rng.luck_roll(success_rate, player.get("fortune", 1000))

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
        return {
            "ok": True,
            "success": False,
            "rate": round(success_rate * 100, 1),
            "text": f"💥 突破失败！损失 {lost} 修为，陷入瓶颈（{constants.BOTTLENECK_MINUTES} 分钟内无法再次突破）。"
                    f"\n💡 可服用「破境丹」提高成功率",
        }

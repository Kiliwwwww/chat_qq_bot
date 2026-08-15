"""丹药服用系统。

玩家可服用背包中的丹药获得修为/气运/回血/复活/PK 增益等效果。
支持一次服用多颗：服用 <丹药名> <数量>
"""

from .. import constants
from ..state import db
from . import combat, debuff, rng

# 属性丹药效果键（攻击/防御/气血/气运），这类丹药受服用次数上限限制（修为丹药不受限）
_ATTRIBUTE_EFFECT_KEYS = ("attack", "defense", "hp", "fortune")


def use_pill(group_id: int, user_id: int, pill_key: str, quantity: int = 1) -> dict:
    """服用丹药，返回结果 dict（灵修/蛊修通用，蛊修的修为丹转化为参悟）"""
    import time

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    is_gu = player.get("cultivation_path") == "gu"

    item = constants.ITEMS.get(pill_key)
    if not item or item.get("type") != "pill":
        return {"ok": False, "text": "没有这种丹药"}

    effect = item.get("effect", {})
    if not effect:
        return {"ok": False, "text": f"【{item['name']}】无法直接服用"}

    # 特殊丹药引导
    if "breakthrough" in effect:
        if is_gu:
            return {"ok": False, "text": f"【{item['name']}】在「蛊修突破 用破境丹」时使用效果最佳"}
        return {"ok": False, "text": f"【{item['name']}】在「突破」时使用效果最佳（发送「突破 用破境丹」）"}
    if "pet_exp" in effect:
        if is_gu:
            # 蛊修：喂养丹转化为给全部蛊虫喂食
            if quantity <= 0:
                return {"ok": False, "text": "数量必须为正数"}
            have = db.get_item_quantity(group_id, user_id, pill_key)
            if have < quantity:
                return {"ok": False, "text": f"你没有足够【{item['name']}】（当前 {have}，需要 {quantity}）"}
            gus = db.get_gus(group_id, user_id)
            if not gus:
                return {"ok": False, "text": "你没有蛊虫，喂养丹无用"}
            db.remove_item(group_id, user_id, pill_key, quantity)
            for g in gus:
                db.update_gu(group_id, user_id, g["id"], {"hunger": max(0, g["hunger"] - 50 * quantity), "last_fed": time.time()})
            return {"ok": True, "text": f"🍖 服用【{item['name']}】×{quantity}，所有蛊虫饱食度恢复！"}
        return {"ok": False, "text": f"【{item['name']}】用于喂养灵宠，请发送「喂养 <编号>」使用"}

    if quantity <= 0:
        return {"ok": False, "text": "数量必须为正数"}

    have = db.get_item_quantity(group_id, user_id, pill_key)
    if have < quantity:
        return {"ok": False, "text": f"你没有足够【{item['name']}】（当前 {have}，需要 {quantity}），可在「商城」购买或「炼丹」炼制"}

    # 涅槃丹：需归西状态才可复活（无论数量，复活一次即可）
    if "revive" in effect:
        if not combat.is_dead(player):
            return {"ok": False, "text": "你并未归西，无需涅槃复活"}
        quantity = 1

    # 洗髓丹：灵修专属（蛊修无灵根品质）
    if "upgrade_quality" in effect:
        if is_gu:
            return {"ok": False, "text": "你是蛊修，不修灵根品质，洗髓丹对你无效"}
        quality_order = constants.QUALITY_ORDER
        if player.get("spirit_quality") not in quality_order:
            return {"ok": False, "text": "灵根品质异常，无法服用"}
        if player["spirit_quality"] == quality_order[-1]:
            return {"ok": False, "text": "你的灵根品质已达【仙品】，无法再提升"}
        # 可提升的层级数（数量超过则只提升到仙品）
        cur_idx = quality_order.index(player["spirit_quality"])
        quantity = min(quantity, len(quality_order) - 1 - cur_idx)

    # 属性丹药服用上限：攻击/防御/气血/气运类丹药每人最多服用 PILL_ATTRIBUTE_MAX_USES 次
    is_attribute_pill = any(k in effect for k in _ATTRIBUTE_EFFECT_KEYS)
    attr_capped_note = ""
    if is_attribute_pill:
        attr_used = db.get_pill_usage(group_id, user_id, pill_key)
        attr_limit = constants.PILL_ATTRIBUTE_MAX_USES
        if attr_used >= attr_limit:
            return {"ok": False, "text": f"【{item['name']}】已服用达到上限（{attr_limit} 次），无法再服用"}
        remain = attr_limit - attr_used
        if quantity > remain:
            attr_capped_note = f"\n⚠️ 已达服用上限，本次只能服用 {remain} 颗"
            quantity = remain

    db.remove_item(group_id, user_id, pill_key, quantity)
    if is_attribute_pill:
        db.add_pill_usage(group_id, user_id, pill_key, quantity)

    lines = [f"💊 服用【{item['name']}】×{quantity} 成功！"]
    fortune = player.get("fortune", 1000)

    # ===== 可叠加效果（按数量累计） =====

    if "progress" in effect:
        gain = effect["progress"]
        # 服丹效果受灵根品质与气运加成（蛊修无灵根品质）
        if is_gu:
            quality_mult = 1.0
        else:
            quality_mult = 1 + constants.QUALITIES.get(player.get("spirit_quality", "废品"), 0.05)
        luck_mult = 1 + rng_factor(fortune) * 2

        # 同种修为丹药效果递减：越吃越差，第 5 次降到最低 50%
        used = db.get_pill_usage(group_id, user_id, pill_key)
        eff_total = sum(_pill_effectiveness(used + i) for i in range(quantity))
        db.add_pill_usage(group_id, user_id, pill_key, quantity)

        # 药王体：修为丹药效果+25%（仅灵修体质）
        pill_mult = 1.25 if player.get("physique") == "yaowang_ti" else 1.0
        final_gain = int(gain * quality_mult * luck_mult * eff_total * pill_mult)
        if is_gu:
            gu_realm = player.get("gu_realm", 0)
            cap = constants.GU_REALM_CAPACITY[gu_realm]
            current = min(cap, player.get("gu_cond", 0) + final_gain)
            db.update_player(group_id, user_id, {"gu_cond": current})
            lines.append(f"✨ 参悟 +{final_gain}！")
        else:
            realm_index = player.get("realm", 0)
            capacity = constants.REALMS[realm_index]["capacity"]
            current = player.get("realm_progress", 0) + final_gain
            if capacity:
                current = min(current, capacity)
            db.update_player(group_id, user_id, {"realm_progress": current})
            lines.append(f"✨ 修为 +{final_gain}！")
        if used > 0:
            avg_eff = int(eff_total / quantity * 100)
            lines.append(f"💊 同种丹药吃多了效果衰减，本次约 {avg_eff}%（最低 50%）")

    if "fortune" in effect:
        gain = effect["fortune"] * quantity
        db.update_player(group_id, user_id, {"fortune": fortune + gain})
        lines.append(f"🍀 气运 +{gain}！")

    if "attack" in effect:
        gain = effect["attack"] * quantity
        db.update_player(group_id, user_id, {"attack": player.get("attack", 10) + gain})
        lines.append(f"⚔️ 攻击 +{gain}！")

    if "defense" in effect:
        gain = effect["defense"] * quantity
        db.update_player(group_id, user_id, {"defense": player.get("defense", 10) + gain})
        lines.append(f"🛡️ 防御 +{gain}！")

    if "hp" in effect:
        gain = effect["hp"] * quantity
        new_hp = player.get("hp", 100) + gain
        db.update_player(group_id, user_id, {"hp": new_hp, "cur_hp": combat.get_cur_hp(player) + gain})
        lines.append(f"❤️ 气血上限 +{gain}！")

    if "heal" in effect:
        result = combat.heal(group_id, user_id, effect["heal"] * quantity)
        lines.append(f"💚 恢复气血 {effect['heal'] * quantity}（当前 {result['hp']}/{result['max_hp']}）")

    if "heal_full" in effect:
        result = combat.heal_full(group_id, user_id)
        lines.append(f"💚 气血回满（{result['hp']}/{result['max_hp']}）")

    if "upgrade_quality" in effect:
        quality_order = constants.QUALITY_ORDER
        cur_idx = quality_order.index(player["spirit_quality"])
        new_quality = quality_order[cur_idx + quantity]
        db.update_player(group_id, user_id, {"spirit_quality": new_quality})
        lines.append(f"💠 洗髓伐骨！灵根品质提升至【{new_quality}】！")

    # ===== 一次性效果 =====

    if "revive" in effect:
        result = combat.revive_now(group_id, user_id)
        if result["ok"]:
            lines.append(result["text"])

    if "pk_boost" in effect:
        boost = effect["pk_boost"]
        hp_cost = effect.get("hp_cost", 0)
        db.update_player(group_id, user_id, {"pk_boost": boost, "pk_hp_cost": hp_cost})
        lines.append(f"💥 狂暴之力附体！下次 PK 战力 +{int(boost * 100)}%，但 PK 后将额外损失 {hp_cost} 点气血")

    # 服用丹药过多可能丹药中毒（同种丹药吃得越多越容易，触发时立即损失修为/参悟）
    if "progress" in effect:
        used = db.get_pill_usage(group_id, user_id, pill_key)
        poison_chance = min(0.30, constants.DEBUFF_TRIGGER["pill_zhongdu_base"] + used * 0.03)
        if rng.luck_roll(poison_chance, fortune):
            d = debuff.add_debuff(group_id, user_id, "danyao_zhongdu")
            cur_player = db.get_player(group_id, user_id)
            if is_gu:
                lost = int(cur_player.get("gu_cond", 0) * constants.PILL_POISON_PROGRESS_LOSS)
                db.update_player(group_id, user_id, {"gu_cond": max(0, cur_player.get("gu_cond", 0) - lost)})
                lines.append(f"😵 药力过猛中毒！触发【{d['name']}】，立即损失 {lost} 参悟！")
            else:
                lost = int(cur_player.get("realm_progress", 0) * constants.PILL_POISON_PROGRESS_LOSS)
                db.update_player(group_id, user_id, {"realm_progress": max(0, cur_player.get("realm_progress", 0) - lost)})
                lines.append(f"😵 药力过猛中毒！触发【{d['name']}】，立即损失 {lost} 修为！")

    # 属性丹药显示累计服用次数
    if is_attribute_pill:
        attr_used = db.get_pill_usage(group_id, user_id, pill_key)
        lines.append(f"📊 该丹药累计服用 {attr_used}/{constants.PILL_ATTRIBUTE_MAX_USES} 次")
    if attr_capped_note:
        lines.append(attr_capped_note.lstrip("\n"))

    return {"ok": True, "text": "\n".join(lines)}


def rng_factor(fortune: int) -> float:
    """气运修正因子（与 services.rng.fortune_factor 保持一致）"""
    from .rng import fortune_factor
    return fortune_factor(fortune)


def _pill_effectiveness(used_before: int) -> float:
    """同种修为丹药的效果倍率。

    第一次 100%，每多吃一次下降 PILL_DIMINISH_STEP，最低降至 PILL_DIMINISH_MIN（50%）。
    """
    return max(constants.PILL_DIMINISH_MIN, 1.0 - used_before * constants.PILL_DIMINISH_STEP)

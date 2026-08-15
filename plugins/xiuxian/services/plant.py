"""种植系统。

玩家种下灵草种子，等待成熟后收获材料。每个玩家同时只能种一块地。
"""

import time

from .. import constants
from ..state import db
from . import combat, rng, world


def plant(group_id: int, user_id: int, crop_name: str) -> dict:
    """种下作物"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if player.get("cultivation_path") == "gu":
        return {"ok": False, "text": "你是蛊修，不修灵田之道"}

    inv_block = world.invasion_block_text(group_id)
    if inv_block:
        return {"ok": False, "text": inv_block}

    if combat.is_dead(player):
        return {"ok": False, "text": f"你已归西，还需 {combat.dead_remain_seconds(player)} 秒复活，无法种植"}

    crop = None
    for cid, c in constants.CROPS.items():
        if c["name"] == crop_name or cid == crop_name:
            crop = {**c, "id": cid}
            break
    if not crop:
        names = "、".join(c["name"] for c in constants.CROPS.values())
        return {"ok": False, "text": f"没有「{crop_name}」这种作物，可种植：{names}"}

    if db.get_planting(group_id, user_id):
        return {"ok": False, "text": "你的灵田里已有作物在生长，先「收获」吧"}

    seed = crop["seed"]
    if db.get_item_quantity(group_id, user_id, seed) <= 0:
        seed_name = constants.ITEMS.get(seed, {}).get("name", seed)
        return {"ok": False, "text": f"你没有【{seed_name}】，可在「商城」购买或去灵药谷探索获得"}

    if not db.set_planting(group_id, user_id, crop["id"]):
        return {"ok": False, "text": "种植失败，请稍后再试"}

    db.remove_item(group_id, user_id, seed, 1)
    minutes = crop["grow_minutes"]
    return {
        "ok": True,
        "text": f"🌱 你种下了【{crop['name']}】种子！\n⏳ {minutes} 分钟后可「收获」（{crop['desc']}）",
    }


def harvest(group_id: int, user_id: int) -> dict:
    """采摘作物"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}
    if player.get("cultivation_path") == "gu":
        return {"ok": False, "text": "你是蛊修，不修灵田之道"}

    inv_block = world.invasion_block_text(group_id)
    if inv_block:
        return {"ok": False, "text": inv_block}

    planting = db.get_planting(group_id, user_id)
    if not planting:
        return {"ok": False, "text": "你的灵田空空如也，先用「种植 <作物>」种下种子吧"}

    crop = constants.CROPS.get(planting["crop_id"])
    if not crop:
        db.clear_planting(group_id, user_id)
        return {"ok": False, "text": "种植数据异常，已清理"}

    elapsed = time.time() - planting["planted_at"]
    needed = crop["grow_minutes"] * 60
    if elapsed < needed:
        remain = int((needed - elapsed) / 60) + 1
        return {"ok": False, "text": f"【{crop['name']}】还未成熟，还需约 {remain} 分钟"}

    db.clear_planting(group_id, user_id)

    result_item = crop["result"]
    result_name = constants.ITEMS.get(result_item, {}).get("name", result_item)
    quantity = 1
    text = f"🌾 你收获了【{result_name}】×{quantity}！"

    # 气运加成：有机会额外收获
    if rng.luck_roll(0.3, player.get("fortune", 1000)):
        quantity += 1
        text += "\n🍀 天时地利，额外收获 1 株！"

    db.add_item(group_id, user_id, result_item, quantity)
    return {"ok": True, "text": text}


def format_field(group_id: int, user_id: int) -> str:
    """查看灵田状态"""
    planting = db.get_planting(group_id, user_id)
    if not planting:
        crops = "、".join(f"{c['name']}({c['grow_minutes']}分钟)" for c in constants.CROPS.values())
        return f"🌾 灵田空空如也，可种植：{crops}\n💡 使用「种植 <作物>」种下种子，成熟后「收获」"
    crop = constants.CROPS.get(planting["crop_id"])
    if not crop:
        return "🌾 灵田状态异常"
    elapsed = time.time() - planting["planted_at"]
    needed = crop["grow_minutes"] * 60
    if elapsed >= needed:
        return f"🌾 【{crop['name']}】已成熟！快发送「收获」采摘吧"
    remain = int((needed - elapsed) / 60) + 1
    return f"🌾 【{crop['name']}】正在生长，还需约 {remain} 分钟成熟"

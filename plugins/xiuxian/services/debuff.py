"""负面状态（Debuff）系统。

可扩展设计：debuff 定义集中在 constants.DEBUFFS，新增一种状态只需加一项定义，
并在需要的逻辑处调用对应效果函数即可。
"""

import json
import time

from .. import constants
from ..state import db


def parse_debuffs(player: dict) -> list[dict]:
    """解析玩家 debuff 列表并过滤已过期的，返回 [{id, until}]"""
    raw = player.get("debuffs", "") or ""
    now = time.time()
    try:
        items = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        items = []
    return [item for item in items if now < item.get("until", 0)]


def get_active_debuffs(player: dict) -> list[dict]:
    """返回带完整定义的活跃 debuff 列表"""
    result = []
    for item in parse_debuffs(player):
        definition = constants.DEBUFFS.get(item["id"])
        if definition:
            result.append({"id": item["id"], "until": item["until"], **definition})
    return result


def add_debuff(group_id: int, user_id: int, debuff_id: str, duration: int = None) -> dict:
    """为玩家添加/刷新一种 debuff，返回 {added, name}"""
    definition = constants.DEBUFFS.get(debuff_id)
    if not definition:
        return {"added": False, "name": ""}
    dur = duration or definition.get("duration", 180)

    player = db.get_player(group_id, user_id)
    if not player:
        return {"added": False, "name": ""}

    existing = parse_debuffs(player)
    now = time.time()
    added = True
    for item in existing:
        if item["id"] == debuff_id:
            item["until"] = now + dur
            added = False
            break
    if added:
        existing.append({"id": debuff_id, "until": now + dur})
    db.update_player(group_id, user_id, {"debuffs": json.dumps(existing, ensure_ascii=False)})
    return {"added": added, "name": definition["name"]}


# ==================== 效果查询 ====================

def rate_bonus(player: dict) -> float:
    """debuff 对修炼速率的加成（负数为降低）"""
    return sum(d.get("rate", 0.0) for d in get_active_debuffs(player))


def fortune_penalty(player: dict) -> int:
    """debuff 造成的气运减益"""
    return sum(d.get("fortune", 0) for d in get_active_debuffs(player))


def effective_fortune(player: dict) -> int:
    """debuff 影响后的有效气运"""
    return max(0, player.get("fortune", 1000) + fortune_penalty(player))


def damage_per_hour(player: dict) -> float:
    """debuff 造成的持续掉血（每小时）"""
    return sum(d.get("damage_tick", 0.0) for d in get_active_debuffs(player))


def block_cultivate(player: dict) -> bool:
    """是否存在禁止闭关的 debuff"""
    return any(d.get("block_cultivate") for d in get_active_debuffs(player))


def format_debuffs(player: dict) -> str:
    """格式化 debuff 状态文本（无则返回空串）"""
    active = get_active_debuffs(player)
    if not active:
        return ""
    now = time.time()
    lines = ["😵 【负面状态】"]
    for d in active:
        remain = int(d["until"] - now)
        lines.append(f"  {d['name']}（剩余 {remain // 60}分{remain % 60}秒）- {d['desc']}")
    return "\n".join(lines)

"""排行榜服务。"""

from .. import constants
from ..state import db
from . import stats as stats_service

CATEGORIES = {
    "realm": "境界榜",
    "power": "战力榜",
    "wealth": "财富榜",
    "fortune": "气运榜",
    "alchemy": "炼丹榜",
}


def get_ranking(group_id: int, category: str) -> list[dict]:
    """获取排行榜数据（已排序），category 见 CATEGORIES"""
    players = db.execute_raw("SELECT * FROM players WHERE group_id = ?", (group_id,))
    if not players:
        return []

    if category == "realm":
        players.sort(key=lambda p: (p.get("realm", 0), p.get("realm_progress", 0)), reverse=True)
    elif category == "power":
        players.sort(key=lambda p: stats_service.get_power(group_id, p), reverse=True)
    elif category == "wealth":
        players.sort(key=lambda p: p.get("coin", 0), reverse=True)
    elif category == "fortune":
        players.sort(key=lambda p: p.get("fortune", 0), reverse=True)
    elif category == "alchemy":
        players.sort(key=lambda p: (p.get("alchemy_level", 0), p.get("alchemy_exp", 0)), reverse=True)
    else:
        return []

    return players[:10]


def _format_row(group_id: int, player: dict, category: str, index: int) -> str:
    name = player.get("name") or str(player.get("user_id", ""))
    realm_name = constants.REALMS[player.get("realm", 0)]["name"]
    medal = ["🥇", "🥈", "🥉"][index] if index < 3 else f"{index + 1}."
    if category == "realm":
        value = f"{realm_name}（修为 {int(player.get('realm_progress', 0))}）"
    elif category == "power":
        value = f"战力 {stats_service.get_power(group_id, player)}"
    elif category == "wealth":
        value = f"{player.get('coin', 0)} 灵石"
    elif category == "fortune":
        value = f"气运 {player.get('fortune', 0)}"
    elif category == "alchemy":
        value = f"炼丹 {player.get('alchemy_level', 1)} 级"
    else:
        value = ""
    return f"{medal} {name} - {value}"


def format_ranking(group_id: int, category: str) -> str:
    """格式化排行榜文本"""
    title = CATEGORIES.get(category)
    if not title:
        return f"未知排行类别，可选：{'、'.join(CATEGORIES.keys())}"

    data = get_ranking(group_id, category)
    if not data:
        return f"📊 【{title}】暂无数据"

    lines = [f"📊 【{title}】"]
    for i, player in enumerate(data):
        lines.append(_format_row(group_id, player, category, i))
    return "\n".join(lines)

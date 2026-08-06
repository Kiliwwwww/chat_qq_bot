"""功法系统：查看、学习与限制。"""

from .. import constants
from ..state import config, db


def list_gongfas(group_id: int, user_id: int) -> str:
    """格式化玩家已学功法"""
    gongfas = db.get_gongfas(group_id, user_id)
    if not gongfas:
        return "📜 你还没有学习任何功法"

    lines = ["📜 【我的功法】"]
    for g in gongfas:
        info = constants.GONGFA_BY_ID.get(g["gongfa_id"])
        if not info:
            continue
        prof = constants.PROFICIENCIES[g.get("level", 0)]
        mult = constants.PROFICIENCY_MULT[g.get("level", 0)]
        lines.append(f"  {info['name']}（{info['root']}系）· {prof}（{int(mult)}倍）")
    lines.append("💡 修炼时会自动提升功法熟练度；「学习功法 <名称>」可学习更多")
    return "\n".join(lines)


def learn_gongfa(group_id: int, user_id: int, gongfa_name: str) -> dict:
    """学习功法"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    gongfa = constants.GONGFA_BY_NAME.get(gongfa_name)
    if not gongfa:
        return {"ok": False, "text": f"未找到功法「{gongfa_name}」，可用的功法请发送「功法图鉴」查看"}

    # 灵根限制：空灵根可学所有属性，其他只能学对应属性
    if player["spirit_root"] != "空" and gongfa["root"] != player["spirit_root"]:
        root_name = constants.SPIRIT_ROOTS[player["spirit_root"]]["name"]
        return {"ok": False, "text": f"你是{root_name}，只能学习{player['spirit_root']}系功法"}

    # 是否已学
    if db.get_gongfa(group_id, user_id, gongfa["id"]):
        return {"ok": False, "text": f"你已经学会了「{gongfa['name']}」"}

    # 数量限制
    if len(db.get_gongfas(group_id, user_id)) >= config.max_gongfa:
        return {"ok": False, "text": f"功法数量已达上限（{config.max_gongfa} 本），先练精再学新吧"}

    # 费用
    cost = config.learn_gongfa_cost * (1 + player.get("realm", 0))
    if player.get("coin", 0) < cost:
        return {"ok": False, "text": f"灵石不足，学习功法需要 {cost} 灵石"}

    if not db.learn_gongfa(group_id, user_id, gongfa["id"]):
        return {"ok": False, "text": "学习功法失败，请稍后再试"}

    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - cost})
    return {"ok": True, "text": f"📜 成功领悟功法【{gongfa['name']}】（{gongfa['root']}系）！\n{gongfa['desc']}"}


def gongfa_catalog() -> str:
    """功法图鉴"""
    lines = ["📚 【功法图鉴】（普通灵根仅可学对应属性，空灵根可学所有）"]
    for root, gongfas in constants.GONGFAS.items():
        lines.append(f"\n【{constants.SPIRIT_ROOTS[root]['name']}】")
        for g in gongfas:
            lines.append(f"  {g['name']} - {g['desc']}")
    return "\n".join(lines)

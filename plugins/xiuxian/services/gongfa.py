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
        level = g.get("level", 0)
        prof = constants.PROFICIENCIES[level]
        mult = constants.PROFICIENCY_MULT[level]
        # 显示当前熟练度与下一级所需经验
        exp = int(g.get("exp", 0))
        need = constants.PROFICIENCY_EXP[level + 1] if level < len(constants.PROFICIENCY_EXP) - 1 else None
        if need:
            lines.append(f"  {info['name']}（{info['root']}系）· {prof}（×{mult:g}，exp {exp}/{need}）")
        else:
            lines.append(f"  {info['name']}（{info['root']}系）· {prof}（×{mult:g}·已圆满）")
    lines.append("💡 修炼可自动提升熟练度；「升级功法 <名称>」可花灵石直接突破")
    return "\n".join(lines)


def upgrade_gongfa(group_id: int, user_id: int, gongfa_name: str) -> dict:
    """花费灵石升级功法熟练度"""
    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    gongfa = constants.GONGFA_BY_NAME.get(gongfa_name)
    if not gongfa:
        return {"ok": False, "text": f"未找到功法「{gongfa_name}」，发送「功法」查看已学功法"}

    held = db.get_gongfa(group_id, user_id, gongfa["id"])
    if not held:
        return {"ok": False, "text": f"你还没有学习「{gongfa['name']}」，先「学习功法 {gongfa['name']}」吧"}

    level = held.get("level", 0)
    if level >= len(constants.PROFICIENCIES) - 1:
        return {"ok": False, "text": f"「{gongfa['name']}」已达【极境】，无法继续提升"}

    # 费用随熟练度等级与境界增长
    cost = config.gongfa_upgrade_cost_base * (level + 1) * (1 + player.get("realm", 0))
    if player.get("coin", 0) < cost:
        return {"ok": False, "text": f"灵石不足，升级「{gongfa['name']}」需要 {cost} 灵石"}

    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - cost})
    db.update_gongfa(group_id, user_id, gongfa["id"], {"level": level + 1})

    old_prof = constants.PROFICIENCIES[level]
    new_prof = constants.PROFICIENCIES[level + 1]
    new_mult = constants.PROFICIENCY_MULT[level + 1]
    return {
        "ok": True,
        "text": (
            f"📈 【功法突破】花费 {cost} 灵石！\n"
            f"「{gongfa['name']}」从【{old_prof}】突破至【{new_prof}】！\n"
            f"⚔️ 效果倍率提升至 ×{new_mult:g}，战力与修炼显著增强！"
        ),
    }


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

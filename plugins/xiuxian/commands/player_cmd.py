"""角色创建与状态指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..state import config, db
from ..services import player as player_svc
from ..services import stats as stats_svc
from ..services import gongfa as gongfa_svc
from .helpers import get_nickname, require_game, xiuxian_command, reply_finish

# 修仙入口
xiuxian_cmd = xiuxian_command("我要修仙", aliases={"修仙"}, priority=5, block=True)
# 随机天命
random_fate_cmd = xiuxian_command("随机天命", priority=5, block=True)
# 废材流主角
trash_fate_cmd = xiuxian_command("废材流主角", aliases={"废柴流"}, priority=5, block=True)
# 状态面板
status_cmd = xiuxian_command("我的状态", aliases={"面板", "状态"}, priority=5, block=True)
# 更换体质
change_physique_cmd = xiuxian_command("更换体质", aliases={"换体质", "体质重铸"}, priority=5, block=True)
# 转世重生
rebirth_cmd = xiuxian_command("转世重生", aliases={"转世"}, priority=5, block=True)
# 自杀（清空全部数据）
suicide_cmd = xiuxian_command("自杀", aliases={"兵解"}, priority=5, block=True)
# 帮助
help_cmd = xiuxian_command("修仙帮助", aliases={"修仙说明"}, priority=5, block=True)


@xiuxian_cmd.handle()
async def handle_xiuxian(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(xiuxian_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        text = (
            "🌄 你机缘巧合，踏入修仙之路！\n"
            "请选择你的天命：\n"
            "1️⃣「随机天命」- 随机灵根、品质，可能一鸣惊人\n"
            "2️⃣「废材流主角」- 空灵根废品起步，但气运极高，逆天改命"
        )
        await reply_finish(xiuxian_cmd, event, text)

    gongfa_text = gongfa_svc.list_gongfas(group_id, event.user_id)
    await reply_finish(xiuxian_cmd, event, player_svc.format_player_profile(group_id, player, gongfa_text))


async def _create_and_finish(cmd, bot, event, talent: str):
    group_id = await require_game(cmd, event)

    name = await get_nickname(bot, group_id, event.user_id)
    ok, msg, data = player_svc.create_character(group_id, event.user_id, name, talent)
    if not ok:
        await reply_finish(cmd, event, msg)

    if talent == "trash":
        intro = (
            f"🌱 【废材流主角】你乃空灵根废品，被世人嘲笑为废柴。\n"
            f"但你的气运高达 {constants.TRASH_FORTUNE}，是天道的宠儿！\n"
            f"前期修炼缓慢，但奇遇不断，终将逆天改命！"
        )
    else:
        root_name = constants.SPIRIT_ROOTS[data["spirit_root"]]["name"]
        quality = data["spirit_quality"]
        intro = (
            f"🌟 【随机天命】你的天命已定！\n"
            f"灵根：{root_name}（{quality}）\n"
            f"气运：{data['fortune']}\n"
            f"祝你在修仙之路上一帆风顺！"
        )
    if data.get("physique"):
        phys = constants.PHYSIQUE_BY_ID.get(data["physique"], {})
        intro += f"\n✨ 天赋异禀！觉醒特殊体质【{phys.get('name', '')}】！"
    intro += "\n\n发送「我的状态」查看面板，或「修仙帮助」查看玩法"
    await reply_finish(cmd, event, intro)


@random_fate_cmd.handle()
async def handle_random_fate(bot: Bot, event, args: Message = CommandArg()):
    await _create_and_finish(random_fate_cmd, bot, event, "random")


@trash_fate_cmd.handle()
async def handle_trash_fate(bot: Bot, event, args: Message = CommandArg()):
    await _create_and_finish(trash_fate_cmd, bot, event, "trash")


@status_cmd.handle()
async def handle_status(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(status_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        await reply_finish(status_cmd, event, "你还没有修仙角色，发送「我要修仙」开启仙途")

    gongfa_text = gongfa_svc.list_gongfas(group_id, event.user_id)
    panel = player_svc.format_player_profile(group_id, player, gongfa_text)

    # 附加装备与战力信息
    from ..services import inventory as inv_svc
    equip_parts = []
    for slot in ("weapon", "armor", "treasure", "ring", "boots"):
        item_id = player.get(slot, "")
        if item_id:
            parts = item_id.split(":")
            if len(parts) == 3:
                kind = constants.EQUIPMENT_KINDS.get(parts[1], {})
                equip_parts.append(f"{kind.get('name', parts[1])}·{parts[2]}")
    if equip_parts:
        panel += "\n🛡️ 装备：" + "、".join(equip_parts)
    power = stats_svc.get_power(group_id, player)
    panel += f"\n⚔️ 战力：{power}"
    await reply_finish(status_cmd, event, panel)


@change_physique_cmd.handle()
async def handle_change_physique(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(change_physique_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        await reply_finish(change_physique_cmd, event, "你还没有修仙角色，发送「我要修仙」开启仙途")

    target = args.extract_plain_text().strip()
    result = player_svc.change_physique(group_id, event.user_id, target)
    await reply_finish(change_physique_cmd, event, result["text"])


@rebirth_cmd.handle()
async def handle_rebirth(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(rebirth_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        await reply_finish(rebirth_cmd, event, "你还没有修仙角色，发送「我要修仙」开启仙途")

    # 确认参数：必须带「确认」才能执行，防止误触清空数据
    arg = args.extract_plain_text().strip()
    if not arg or "确认" not in arg:
        await reply_finish(rebirth_cmd, event, 
            "🌀 【转世重生】将清空你的修为、功法、背包、灵宠与弟子！\n"
            "保留灵根、品质、体质与天命，并获得永久气运+修炼加成。\n"
            f"⚠️ 至少需要达到【{constants.REALMS[config.rebirth_min_realm]['name']}】境界。\n"
            "确认转世请发送：转世重生 确认"
        )

    result = player_svc.rebirth(group_id, event.user_id)
    await reply_finish(rebirth_cmd, event, result["text"])


@suicide_cmd.handle()
async def handle_suicide(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(suicide_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        await reply_finish(suicide_cmd, event, "你还没有修仙角色，无法自杀")

    # 二次确认，防止误触彻底清空
    arg = args.extract_plain_text().strip()
    if not arg or "确认" not in arg:
        await reply_finish(suicide_cmd, event, 
            "💀 【自杀】将彻底清空你的所有数据！\n"
            "包括：境界、修为、灵石、功法、背包、灵宠、弟子、体质、灵根——一切归零，无法找回！\n"
            "确认自杀请发送：自杀 确认"
        )

    result = player_svc.suicide(group_id, event.user_id)
    await reply_finish(suicide_cmd, event, result["text"])


@help_cmd.handle()
async def handle_help(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(help_cmd, event)

    help_text = (
        "🏯 【修仙世界·指令大全】\n"
        "━━━━━━━━━━━━━━━\n"
        "🆕 新手入门\n"
        "  · 我要修仙      → 创建角色（首次必做）\n"
        "  · 随机天命      → 随机灵根/品质（可能抽到极品！）\n"
        "  · 废材流主角    → 空灵根+废品，但气运极高，逆天改命\n"
        "  · 我的状态      → 查看角色面板\n"
        "  · 更换体质      → 花费灵石重铸特殊体质（指定名称费用更高）\n"
        "  · 转世重生      → 重开数据（需金丹以上），保留灵根/体质，获得永久气运+修炼加成\n"
        "  · 自杀          → 彻底清空全部数据，从头再来（需二次确认）\n"
        "━━━━━━━━━━━━━━━\n"
        "🧘 修炼突破\n"
        "  · 闭关 洞府     → 开始挂机（可选：灵脉/妖兽森林/秘境），挂机可获得修为+灵石\n"
        "  · 出关          → 结算挂机收益（修为、灵石、功法熟练度）\n"
        "  · 突破          → 修为满后冲击下一境界\n"
        "  · 突破 用破境丹 → 服用破境丹再突破，成功率更高\n"
        "  · 突破需消耗对应药材+丹药：妖兽森林/秘境/古神药园/灵药谷均可刷取；也可等「突破商人」现身坊市直接购买\n"
        "  · 世界          → 查看当前世界事件/天气/秘境状态\n"
        "  · 触发事件 上古秘境开启 → 管理员手动触发世界事件（发送「触发事件 无」清除）\n"
        "  · 召唤商人      → 管理员手动召唤突破商人（专售突破大境界药材/丹药）\n"
        "━━━━━━━━━━━━━━━\n"
        "🗺️ 探索获取资源\n"
        "  · 探索 洞府     → 常开地点：洞府/灵脉/妖兽森林\n"
        "  · 探索 妖兽森林 → 高收益，可能遇险\n"
        "  · 探索 秘境     → 限时开放！需对应世界事件开启\n"
        "  · 限时地图：秘境/灵药谷/万妖山/星辰殿/远古战场/幽冥深渊\n"
        "    分别由 上古秘境/天降灵雨/万兽朝宗/天地异象/道韵弥漫/魔潮汹涌 事件开启\n"
        "  · 古神药园      → 常开副本，可刷高境界突破神药\n"
        "  · 发送「世界」可查看当前开放的限时地图\n"
        "━━━━━━━━━━━━━━━\n"
        "📜 功法\n"
        "  · 功法          → 查看已学功法及熟练度进度\n"
        "  · 功法图鉴      → 查看全部功法\n"
        "  · 学习功法 焚天诀 → 学习新功法（普通灵根只能学对应系）\n"
        "  · 升级功法 焚天诀 → 花灵石直接突破功法熟练度\n"
        "━━━━━━━━━━━━━━━\n"
        "⚗️ 炼丹炼器装备\n"
        "  · 炼丹 修炼丹   → 炼丹（破境丹/回灵丹/大还丹/涅槃丹/狂暴丹等）\n"
        "  · 炼器          → 锻造武器/法袍/法宝/戒指/战靴\n"
        "  · 背包          → 查看物品\n"
        "  · 赠送 @玩家 洗髓丹 3 → 把背包物品赠送给他人\n"
        "  · 装备 神兵·仙器 → 穿戴装备\n"
        "  · 卸下 武器     → 卸下装备\n"
        "━━━━━━━━━━━━━━━\n"
        "💊 丹药商城\n"
        "  · 商城          → 常驻商城，长期出售各种丹药\n"
        "  · 商城购买 聚气散 3 → 按名称+数量购买（也可用编号，如 商城购买 1）\n"
        "  · 商城出售 灵草 5 → 把材料/丹药/装备卖给商城换灵石\n"
        "  · 服用 修炼丹   → 服用丹药（回灵丹回血/大还丹满血/涅槃丹复活/狂暴丹PK加成）\n"
        "━━━━━━━━━━━━━━━\n"
        "⚔️ 战斗系统\n"
        "  · 攻击 @玩家    → PK 对决（按战力分胜负，输家扣血；对同一人 5 分钟冷却）\n"
        "  · 开启生死台 @玩家 → 发起生死台挑战，对方「同意生死台」后自动死斗至一方归西\n"
        "  · 同意生死台    → 应战对方的生死台挑战（输家损失灵石+修为）\n"
        "  · 报名大乱斗    → 5 人混战，最后 2 名胜者各得 1000 灵石\n"
        "  · 大乱斗        → 查看当前报名情况\n"
        "  · 讨伐boss      → 挑战世界 Boss（按战力造成伤害，会被反击扣血，可能掉落丹药/灵兽/功法/突破材料）\n"
        "  · boss状态      → 查看当前 Boss 血量与贡献\n"
        "  · 开启boss      → 管理员手动开启 Boss 挑战（自动刷新保持不变）\n"
        "  · 迎击天魔      → 域外天魔入侵时迎战天魔大军（入侵期间无法修炼/探索/炼丹）\n"
        "  · 天魔状态      → 查看天魔入侵进度\n"
        "  · 血量 0 会归西，60 秒后自动复活；血量过低记得服用回灵丹/大还丹\n"
        "━━━━━━━━━━━━━━━\n"
        "🐾 灵宠\n"
        "  · 灵宠          → 查看灵宠及挂机收益加成\n"
        "  · 灵兽阁        → 花灵石直接购买灵兽（妖兽/神兽/上古异种）\n"
        "  · 灵兽阁购买 1  → 购买指定灵兽（也可按名称，如 灵兽阁购买 神兽）\n"
        "  · 喂养 1        → 用精元丹/凝魄丹喂养升级\n"
        "  · 种植 灵草     → 种下种子，成熟后收获（灵草10分钟/龙涎草30分钟/千年灵参60分钟）\n"
        "  · 收获          → 采摘成熟的作物\n"
        "  · 灵田          → 查看灵田状态\n"
        "━━━━━━━━━━━━━━━\n"
        "🏪 坊市交易\n"
        "  · 坊市          → 查看商人商品与挂单\n"
        "  · 坊市出售 灵草 5 30 → 上架出售\n"
        "  · 坊市购买 3    → 买玩家挂单（也可按物品名，如 坊市购买 灵草）\n"
        "  · 坊市购商 1    → 买神秘商人商品（也可按名称）\n"
        "  · 坊市购突破 1  → 买突破商人商品（也可按名称，如 坊市购突破 聚气草）\n"
        "  · 坊市撤销 3    → 撤销自己的挂单\n"
        "━━━━━━━━━━━━━━━\n"
        "🔥 师徒传功\n"
        "  · 收徒 @玩家    → 收闭关的低境界玩家为弟子（高境界才可）\n"
        "  · 弟子          → 查看自己拥有的弟子\n"
        "  · 传功 1        → 为弟子传功，获得修为（境界越高收益越多）\n"
        "  · 逐出 1        → 逐出弟子（对方恢复自由）\n"
        "  · 叛门          → 被收为弟子后尝试脱离师门（高气运可触发天命觉醒）\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 排行榜\n"
        "  · 修仙排行榜 境界 → 境界/战力/财富/气运/炼丹\n"
        "━━━━━━━━━━━━━━━\n"
        "💡 小贴士\n"
        "  · 挂机收益受灵根品质/功法/地点/世界事件影响\n"
        "  · 气运越高奇遇越多，关注「世界」事件变化！"
    )
    await reply_finish(help_cmd, event, help_text)

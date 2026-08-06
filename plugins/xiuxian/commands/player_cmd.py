"""角色创建与状态指令。"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..state import db
from ..services import player as player_svc
from ..services import stats as stats_svc
from ..services import gongfa as gongfa_svc
from .helpers import get_nickname, require_game

# 修仙入口
xiuxian_cmd = on_command("我要修仙", aliases={"修仙"}, priority=5, block=True)
# 随机天命
random_fate_cmd = on_command("随机天命", priority=5, block=True)
# 废材流主角
trash_fate_cmd = on_command("废材流主角", aliases={"废柴流"}, priority=5, block=True)
# 状态面板
status_cmd = on_command("我的状态", aliases={"面板", "状态"}, priority=5, block=True)
# 更换体质
change_physique_cmd = on_command("更换体质", aliases={"换体质", "体质重铸"}, priority=5, block=True)
# 帮助
help_cmd = on_command("修仙帮助", aliases={"修仙说明"}, priority=5, block=True)


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
        await xiuxian_cmd.finish(text)

    gongfa_text = gongfa_svc.list_gongfas(group_id, event.user_id)
    await xiuxian_cmd.finish(player_svc.format_player_profile(group_id, player, gongfa_text))


async def _create_and_finish(cmd, bot, event, talent: str):
    group_id = await require_game(cmd, event)

    name = await get_nickname(bot, group_id, event.user_id)
    ok, msg, data = player_svc.create_character(group_id, event.user_id, name, talent)
    if not ok:
        await cmd.finish(msg)

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
    await cmd.finish(intro)


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
        await status_cmd.finish("你还没有修仙角色，发送「我要修仙」开启仙途")

    gongfa_text = gongfa_svc.list_gongfas(group_id, event.user_id)
    panel = player_svc.format_player_profile(group_id, player, gongfa_text)

    # 附加装备与战力信息
    from ..services import inventory as inv_svc
    equip_parts = []
    for slot in ("weapon", "armor", "treasure"):
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
    await status_cmd.finish(panel)


@change_physique_cmd.handle()
async def handle_change_physique(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(change_physique_cmd, event)

    player = db.get_player(group_id, event.user_id)
    if not player:
        await change_physique_cmd.finish("你还没有修仙角色，发送「我要修仙」开启仙途")

    target = args.extract_plain_text().strip()
    result = player_svc.change_physique(group_id, event.user_id, target)
    await change_physique_cmd.finish(result["text"])


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
        "━━━━━━━━━━━━━━━\n"
        "🧘 修炼突破\n"
        "  · 闭关 洞府     → 开始挂机（可选：灵脉/妖兽森林/秘境）\n"
        "  · 出关          → 结算挂机收益\n"
        "  · 突破          → 修为满后冲击下一境界\n"
        "  · 突破 用破境丹 → 服用破境丹再突破，成功率更高\n"
        "  · 世界          → 查看当前世界事件/天气/秘境状态\n"
        "━━━━━━━━━━━━━━━\n"
        "🗺️ 探索获取资源\n"
        "  · 探索 洞府     → 探索地点获得资源（有冷却）\n"
        "  · 探索 妖兽森林 → 高收益，可能遇险\n"
        "  · 探索 秘境     → 仅上古秘境开启时可进\n"
        "━━━━━━━━━━━━━━━\n"
        "📜 功法\n"
        "  · 功法          → 查看已学功法\n"
        "  · 功法图鉴      → 查看全部功法\n"
        "  · 学习功法 焚天诀 → 学习新功法（普通灵根只能学对应系）\n"
        "━━━━━━━━━━━━━━━\n"
        "⚗️ 炼丹炼器装备\n"
        "  · 炼丹 修炼丹   → 炼丹（破境丹/回灵丹/精元丹）\n"
        "  · 炼器          → 锻造武器/法袍/法宝\n"
        "  · 背包          → 查看物品\n"
        "  · 装备 神兵·仙器 → 穿戴装备\n"
        "  · 卸下 武器     → 卸下装备\n"
        "━━━━━━━━━━━━━━━\n"
        "💊 丹药商城\n"
        "  · 商城          → 常驻商城，长期出售各种丹药\n"
        "  · 商城购买 1    → 购买丹药\n"
        "  · 服用 修炼丹   → 服用丹药增加修为/气运（聚气散/凝神丹/培元丹/蕴神丹/天机丹等）\n"
        "━━━━━━━━━━━━━━━\n"
        "🐾 灵宠\n"
        "  · 灵宠          → 查看灵宠\n"
        "  · 喂养 1        → 用精元丹喂养升级\n"
        "━━━━━━━━━━━━━━━\n"
        "🏪 坊市交易\n"
        "  · 坊市          → 查看商人商品与挂单\n"
        "  · 坊市出售 灵草 5 30 → 上架出售\n"
        "  · 坊市购买 3    → 买玩家挂单\n"
        "  · 坊市购商 1    → 买神秘商人商品\n"
        "  · 坊市撤销 3    → 撤销自己的挂单\n"
        "━━━━━━━━━━━━━━━\n"
        "🔥 炉鼎互动\n"
        "  · 抓捕 @玩家    → 抓捕闭关的低境界玩家（高境界才可）\n"
        "  · 炉鼎          → 查看自己的炉鼎\n"
        "  · 挣脱          → 被俘后尝试反抗（高气运可触发天命觉醒）\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 排行榜\n"
        "  · 修仙排行榜 境界 → 境界/战力/财富/气运/炼丹\n"
        "━━━━━━━━━━━━━━━\n"
        "💡 小贴士\n"
        "  · 挂机收益受灵根品质/功法/地点/世界事件影响\n"
        "  · 气运越高奇遇越多，关注「世界」事件变化！"
    )
    await help_cmd.finish(help_text)

"""修炼、突破、探索与功法指令。"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from .. import constants
from ..state import db
from ..services import cultivation as cult_svc
from ..services import breakthrough as btk_svc
from ..services import explore as explore_svc
from ..services import gongfa as gongfa_svc
from .helpers import require_game

# 闭关
biguan_cmd = on_command("闭关", priority=5, block=True)
# 出关
chuguan_cmd = on_command("出关", priority=5, block=True)
# 突破
tupo_cmd = on_command("突破", priority=5, block=True)
# 探索
tansuo_cmd = on_command("探索", priority=5, block=True)
# 功法
gongfa_cmd = on_command("功法", aliases={"我的功法"}, priority=5, block=True)
# 学习功法
learn_gongfa_cmd = on_command("学习功法", aliases={"学功法"}, priority=5, block=True)
# 功法图鉴
catalog_cmd = on_command("功法图鉴", priority=5, block=True)


@biguan_cmd.handle()
async def handle_biguan(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(biguan_cmd, event)

    location = args.extract_plain_text().strip() or "洞府"
    ok, result = cult_svc.start_cultivating(group_id, event.user_id, location)
    if not ok:
        await biguan_cmd.finish(result)

    player = db.get_player(group_id, event.user_id)
    rate = cult_svc.calculate_rate(group_id, player, result)
    location_cfg = constants.LOCATIONS[result]
    await biguan_cmd.finish(
        f"🧘 你选择在【{result}】开始闭关！\n"
        f"📈 当前修炼速率：{int(rate)} 修为/小时\n"
        f"💡 {location_cfg['desc']}\n"
        f"随时发送「出关」结算收益"
    )


@chuguan_cmd.handle()
async def handle_chuguan(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(chuguan_cmd, event)

    result = cult_svc.settle_cultivation(group_id, event.user_id)
    if not result["ok"]:
        await chuguan_cmd.finish(result["text"])
    await chuguan_cmd.finish(cult_svc.format_settle_result(group_id, result))


@tupo_cmd.handle()
async def handle_tupo(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(tupo_cmd, event)

    arg_text = args.extract_plain_text().strip()
    use_pill = "破境丹" in arg_text or "用" in arg_text

    result = btk_svc.attempt_breakthrough(group_id, event.user_id, use_pill=use_pill)
    if not result["ok"]:
        await tupo_cmd.finish(result["text"])
    if result["success"]:
        await tupo_cmd.finish(
            f"{result['text']}\n"
            f"📊 突破成功率：{result['rate']}%\n"
            f"🎯 继续「闭关」修炼，冲击更高境界！"
        )
    else:
        await tupo_cmd.finish(
            f"{result['text']}\n"
            f"📊 突破成功率：{result['rate']}%\n"
            f"💡 提升灵根品质、服用破境丹、等待灵气潮汐可提高成功率"
        )


@tansuo_cmd.handle()
async def handle_tansuo(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(tansuo_cmd, event)

    location = args.extract_plain_text().strip() or "洞府"
    result = explore_svc.explore(group_id, event.user_id, location)
    if not result["ok"]:
        await tansuo_cmd.finish(result["text"])
    await tansuo_cmd.finish(result["text"])


@gongfa_cmd.handle()
async def handle_gongfa(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(gongfa_cmd, event)
    await gongfa_cmd.finish(gongfa_svc.list_gongfas(group_id, event.user_id))


@learn_gongfa_cmd.handle()
async def handle_learn_gongfa(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(learn_gongfa_cmd, event)

    name = args.extract_plain_text().strip()
    if not name:
        await learn_gongfa_cmd.finish("请指定功法名称，如：学习功法 焚天诀（发送「功法图鉴」查看所有功法）")
    result = gongfa_svc.learn_gongfa(group_id, event.user_id, name)
    if result["ok"]:
        await learn_gongfa_cmd.finish(result["text"])
    else:
        await learn_gongfa_cmd.finish(result["text"])


@catalog_cmd.handle()
async def handle_catalog(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(catalog_cmd, event)
    await catalog_cmd.finish(gongfa_svc.gongfa_catalog())

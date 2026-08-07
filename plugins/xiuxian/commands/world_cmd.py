"""世界状态指令。"""

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..state import config
from ..services import world as world_svc
from .helpers import require_game, xiuxian_command, reply_finish

world_cmd = xiuxian_command("世界", aliases={"世界状态"}, priority=5, block=True)
trigger_event_cmd = xiuxian_command("触发事件", aliases={"手动事件"}, priority=5, block=True)
summon_merchant_cmd = xiuxian_command("召唤商人", aliases={"刷新商人", "召唤突破商人"}, priority=5, block=True)


@world_cmd.handle()
async def handle_world(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(world_cmd, event)

    world_svc.ensure_world(group_id)
    await reply_finish(world_cmd, event, world_svc.format_world_status(group_id))


@trigger_event_cmd.handle()
async def handle_trigger_event(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(trigger_event_cmd, event)

    # 仅管理员可触发
    if event.user_id != config.admin_qq:
        await reply_finish(trigger_event_cmd, event, "⛔ 只有管理员可以触发世界事件")

    name = args.extract_plain_text().strip()
    if not name:
        await reply_finish(
            trigger_event_cmd,
            event,
            "请指定事件名称，如：触发事件 上古秘境开启\n可选：灵气潮汐/妖兽暴动/上古秘境开启/天地异象/天降灵雨/道韵弥漫/万兽朝宗/仙缘降临/魔潮汹涌\n发送「触发事件 无」可清除当前事件",
        )

    result = world_svc.trigger_event(group_id, name)
    if not result["ok"]:
        await reply_finish(trigger_event_cmd, event, result["text"])

    # 主动向全群发送事件公告（与自动事件推送一致）
    try:
        await bot.send_group_msg(group_id=group_id, message=result["text"])
        logger.info(f"群 {group_id} 手动触发事件公告已推送: {result['text'][:30]}")
    except Exception as e:
        logger.error(f"群 {group_id} 手动事件公告推送失败: {e}")

    await reply_finish(trigger_event_cmd, event, "✅ 事件已触发，已向全群公告！")


@summon_merchant_cmd.handle()
async def handle_summon_merchant(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(summon_merchant_cmd, event)

    # 仅管理员可召唤突破商人
    if event.user_id != config.admin_qq:
        await reply_finish(summon_merchant_cmd, event, "⛔ 只有管理员可以召唤突破商人")

    text = world_svc.summon_breakthrough_merchant(group_id)

    # 主动向全群推送公告
    try:
        await bot.send_group_msg(group_id=group_id, message=text)
        logger.info(f"群 {group_id} 管理员手动召唤突破商人，已推送公告")
    except Exception as e:
        logger.error(f"群 {group_id} 突破商人公告推送失败: {e}")

    await reply_finish(summon_merchant_cmd, event, "✅ 突破商人已召唤，已向全群公告！")

"""域外天魔入侵指令。"""

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..state import config
from ..services import invasion as invasion_svc
from .helpers import require_game, xiuxian_command, reply_finish

# 迎击天魔
invasion_attack_cmd = xiuxian_command("迎击天魔", aliases={"迎战天魔", "打天魔", "抵御天魔"}, priority=5, block=True)
# 查看入侵状态
invasion_status_cmd = xiuxian_command("天魔状态", aliases={"入侵状态", "天魔入侵"}, priority=5, block=True)
# 管理员手动开启入侵
invasion_start_cmd = xiuxian_command("开启入侵", aliases={"开启天魔入侵", "召唤天魔"}, priority=5, block=True)
# 管理员手动提前结束入侵
invasion_end_cmd = xiuxian_command("结束入侵", aliases={"结算入侵", "提前结算入侵", "关闭入侵"}, priority=5, block=True)


@invasion_attack_cmd.handle()
async def handle_invasion_attack(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(invasion_attack_cmd, event)
    result = invasion_svc.attack_demon(group_id, event.user_id)
    await reply_finish(invasion_attack_cmd, event, result["text"])


@invasion_status_cmd.handle()
async def handle_invasion_status(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(invasion_status_cmd, event)
    await reply_finish(invasion_status_cmd, event, invasion_svc.format_status(group_id))


@invasion_start_cmd.handle()
async def handle_invasion_start(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(invasion_start_cmd, event)

    if event.user_id != config.admin_qq:
        await reply_finish(invasion_start_cmd, event, "⛔ 只有管理员可以手动开启域外天魔入侵")

    announcement = invasion_svc.force_start(group_id)
    if not announcement.startswith("🌑"):
        await reply_finish(invasion_start_cmd, event, announcement)

    # 主动向全群推送公告
    try:
        await bot.send_group_msg(group_id=group_id, message=announcement)
        logger.info(f"群 {group_id} 管理员手动开启域外天魔入侵，已推送公告")
    except Exception as e:
        logger.error(f"群 {group_id} 天魔入侵公告推送失败: {e}")

    await reply_finish(invasion_start_cmd, event, "✅ 域外天魔入侵已开启，已向全群公告！")


@invasion_end_cmd.handle()
async def handle_invasion_end(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(invasion_end_cmd, event)

    if event.user_id != config.admin_qq:
        await reply_finish(invasion_end_cmd, event, "⛔ 只有管理员可以提前结束域外天魔入侵")

    result = invasion_svc.force_end(group_id)
    if not result.startswith("🌄"):
        await reply_finish(invasion_end_cmd, event, result)

    # 主动向全群推送结算公告
    try:
        await bot.send_group_msg(group_id=group_id, message=result)
        logger.info(f"群 {group_id} 管理员手动结算域外天魔入侵，已推送公告")
    except Exception as e:
        logger.error(f"群 {group_id} 天魔入侵结算公告推送失败: {e}")

    await reply_finish(invasion_end_cmd, event, "✅ 域外天魔入侵已结束结算，已向全群公告！")

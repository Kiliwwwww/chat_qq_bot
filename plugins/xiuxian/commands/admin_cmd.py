"""修仙功能开关指令（仅管理员，每个群独立生效）。"""

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..state import config, db
from .helpers import require_group, xiuxian_command, reply_finish

# 开启修仙
game_on_cmd = xiuxian_command("开启修仙", aliases={"开启修仙功能"}, priority=5, block=True)
# 关闭修仙
game_off_cmd = xiuxian_command("关闭修仙", aliases={"关闭修仙功能"}, priority=5, block=True)


@game_on_cmd.handle()
async def handle_game_on(bot: Bot, event, args: Message = CommandArg()):
    group_id = require_group(event)
    if not group_id:
        await reply_finish(game_on_cmd, event, "请在群聊中使用「开启修仙」")

    if event.user_id != config.admin_qq:
        await reply_finish(game_on_cmd, event, "⛔ 只有管理员可以操作修仙功能开关")

    if db.set_game_enabled(group_id, True):
        logger.info(f"群 {group_id} 修仙功能已开启（操作者 {event.user_id}）")
        await reply_finish(game_on_cmd, event, "✅ 本群修仙功能已开启，道友们可以开始修炼了！")
    await reply_finish(game_on_cmd, event, "操作失败，请稍后再试")


@game_off_cmd.handle()
async def handle_game_off(bot: Bot, event, args: Message = CommandArg()):
    group_id = require_group(event)
    if not group_id:
        await reply_finish(game_off_cmd, event, "请在群聊中使用「关闭修仙」")

    if event.user_id != config.admin_qq:
        await reply_finish(game_off_cmd, event, "⛔ 只有管理员可以操作修仙功能开关")

    if db.set_game_enabled(group_id, False):
        logger.info(f"群 {group_id} 修仙功能已关闭（操作者 {event.user_id}）")
        await reply_finish(game_off_cmd, event, "⛔ 本群修仙功能已关闭，玩家数据将保留，管理员发送「开启修仙」可重新启用")
    await reply_finish(game_off_cmd, event, "操作失败，请稍后再试")

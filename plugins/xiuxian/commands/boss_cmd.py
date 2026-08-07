"""世界 Boss 指令。"""

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..state import config
from ..services import boss as boss_svc
from .helpers import require_game, xiuxian_command, reply_finish

boss_attack_cmd = xiuxian_command("讨伐boss", aliases={"讨伐", "打boss"}, priority=5, block=True)
boss_status_cmd = xiuxian_command("boss状态", aliases={"boss", "世界boss"}, priority=5, block=True)
boss_spawn_cmd = xiuxian_command("开启boss", aliases={"开启boss挑战", "刷新boss"}, priority=5, block=True)


@boss_attack_cmd.handle()
async def handle_boss_attack(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(boss_attack_cmd, event)

    result = boss_svc.attack_boss(group_id, event.user_id)
    await reply_finish(boss_attack_cmd, event, result["text"])


@boss_status_cmd.handle()
async def handle_boss_status(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(boss_status_cmd, event)

    await reply_finish(boss_status_cmd, event, boss_svc.format_boss_status(group_id))


@boss_spawn_cmd.handle()
async def handle_boss_spawn(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(boss_spawn_cmd, event)

    # 仅管理员可手动开启 Boss
    if event.user_id != config.admin_qq:
        await reply_finish(boss_spawn_cmd, event, "⛔ 只有管理员可以手动开启 Boss 挑战")

    announcement = boss_svc.force_spawn(group_id)
    if not announcement:
        await reply_finish(boss_spawn_cmd, event, "无法开启：已有 Boss 在场，或群内没有玩家")

    # 主动向全群推送公告
    try:
        await bot.send_group_msg(group_id=group_id, message=announcement)
        logger.info(f"群 {group_id} 管理员手动开启 Boss，已推送公告")
    except Exception as e:
        logger.error(f"群 {group_id} Boss 公告推送失败: {e}")

    await reply_finish(boss_spawn_cmd, event, "✅ Boss 已开启，已向全群公告！")

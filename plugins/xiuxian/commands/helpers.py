"""命令层公共工具。"""

from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent

from ..state import db


def require_group(event: MessageEvent) -> int:
    """校验群聊消息，非群聊返回 0（调用方据此提示）"""
    if not isinstance(event, GroupMessageEvent):
        return 0
    return event.group_id


async def require_game(matcher, event: MessageEvent) -> int:
    """校验群聊消息且本群修仙功能已开启。

    不满足时直接结束当前指令并提示，返回群号供后续使用。
    """
    group_id = require_group(event)
    if not group_id:
        await matcher.finish("修仙游戏只在群聊中生效哦")
    if not db.is_game_enabled(group_id):
        await matcher.finish("⛔ 本群修仙功能已关闭，管理员发送「开启修仙」可重新启用")
    return group_id


async def get_nickname(bot, group_id: int, user_id: int) -> str:
    """获取用户在群内的昵称（群名片优先，其次 QQ 昵称，最后 QQ 号）"""
    try:
        info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        return info.get("card") or info.get("nickname") or str(user_id)
    except Exception:
        return str(user_id)

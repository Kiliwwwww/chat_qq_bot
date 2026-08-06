"""命令层公共工具。"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent, MessageSegment
from nonebot.rule import Rule

from ..state import db


def strict_command_rule(*names: str) -> Rule:
    """严格命令匹配规则。

    仅当消息纯文本**完全等于**命令名，或为「命令名 + 空格 + 参数」时才匹配，
    避免用户消息中偶然包含关键词（如「我想看下修仙帮助」）被误判为命令。
    """
    async def _check(event: MessageEvent) -> bool:
        text = event.get_plaintext().strip()
        for name in names:
            if text == name or text.startswith(name + " "):
                return True
        return False
    return Rule(_check)


def xiuxian_command(cmd: str, aliases=None, **kwargs):
    """注册修仙指令：自动附加严格匹配规则，命令必须整串匹配才生效。"""
    names = [cmd] + list(aliases or [])
    return on_command(
        cmd,
        aliases=aliases,
        rule=strict_command_rule(*names),
        **kwargs,
    )


async def reply_finish(matcher, event: MessageEvent, content):
    """以「引用回复」的形式结束指令，回复会引用用户的原消息。"""
    msg = MessageSegment.reply(event.message_id) + content
    await matcher.finish(msg)


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
        await reply_finish(matcher, event, "修仙游戏只在群聊中生效哦")
    if not db.is_game_enabled(group_id):
        await reply_finish(matcher, event, "⛔ 本群修仙功能已关闭，管理员发送「开启修仙」可重新启用")
    return group_id


async def get_nickname(bot, group_id: int, user_id: int) -> str:
    """获取用户在群内的昵称（群名片优先，其次 QQ 昵称，最后 QQ 号）"""
    try:
        info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        return info.get("card") or info.get("nickname") or str(user_id)
    except Exception:
        return str(user_id)

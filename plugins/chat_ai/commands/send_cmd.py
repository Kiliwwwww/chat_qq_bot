from nonebot import on_command, get_plugin_config, get_bot, logger
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.exception import FinishedException
from nonebot.params import CommandArg

from ..config import Config

send_cmd = on_command("send", priority=5, block=True)


@send_cmd.handle()
async def handle_send(event: MessageEvent, args: Message = CommandArg()):
    """管理员向指定QQ群发送消息：send <群号> <内容>"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await send_cmd.finish("只有管理员可以使用此命令")

    arg_text = args.extract_plain_text().strip()
    parts = arg_text.split(maxsplit=1)
    if len(parts) < 2:
        await send_cmd.finish("用法：send <群号> <内容>")

    group_token, content = parts[0], parts[1].strip()
    if not group_token.isdigit():
        await send_cmd.finish("群号必须是数字")
    if not content:
        await send_cmd.finish("消息内容不能为空")
    group_id = int(group_token)

    try:
        bot = get_bot()
        await bot.send_group_msg(group_id=group_id, message=content)
        logger.info(f"管理员向群 {group_id} 发送消息: {content[:30]}")
        await send_cmd.finish(f"已发送到群 {group_id}")
    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"发送消息到群 {group_id} 失败: {e}")
        await send_cmd.finish(f"发送失败: {e}")

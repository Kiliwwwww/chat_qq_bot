import time

from nonebot import on_command, get_plugin_config, logger
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg

from ..config import Config
from .. import state
from ..state import db, auto_emoji_users, auto_emoji_groups

mute_cmd = on_command("闭嘴", priority=5, block=True)
emoji_cmd = on_command("贴表情", priority=5, block=True)
emoji_cancel_cmd = on_command("取消贴表情", priority=5, block=True)
group_emoji_cmd = on_command("全体贴表情", priority=5, block=True)
group_emoji_cancel_cmd = on_command("取消全体贴表情", priority=5, block=True)
setkey_cmd = on_command("setkey", aliases={"设置关键词"}, priority=5, block=True)
settings_cmd = on_command("settings", aliases={"设置"}, priority=5, block=True)
groupsettings_cmd = on_command("groupsettings", aliases={"群设置"}, priority=5, block=True)


@mute_cmd.handle()
async def handle_mute(event: MessageEvent):
    """处理闭嘴命令（仅管理员可用）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await mute_cmd.finish("权限不足，仅管理员可使用此命令")

    # 设置禁言5分钟
    state.bot_mute_until = time.time() + 300
    logger.info(f"管理员触发闭嘴，bot将静默5分钟")
    await mute_cmd.finish("好的，我闭嘴5分钟")


@emoji_cmd.handle()
async def handle_emoji(event: GroupMessageEvent, args: Message = CommandArg()):
    """处理贴表情命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await emoji_cmd.finish("权限不足，仅管理员可使用此命令")

    # 解析QQ号
    arg = args.extract_plain_text().strip()
    if not arg:
        await emoji_cmd.finish("请指定QQ号，格式：贴表情 <QQ号>")

    try:
        target_qq = int(arg)
    except ValueError:
        await emoji_cmd.finish("请输入有效的QQ号")

    group_id = event.group_id

    # 添加到自动贴表情列表
    auto_emoji_users.add((group_id, target_qq))
    logger.info(f"管理员设置了自动给用户 {target_qq} 在群 {group_id} 贴表情")
    await emoji_cmd.finish(f"已开启自动给该用户消息贴表情")


@emoji_cancel_cmd.handle()
async def handle_emoji_cancel(event: GroupMessageEvent, args: Message = CommandArg()):
    """处理取消贴表情命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await emoji_cancel_cmd.finish("权限不足，仅管理员可使用此命令")

    # 解析QQ号
    arg = args.extract_plain_text().strip()
    if not arg:
        await emoji_cancel_cmd.finish("请指定QQ号，格式：取消贴表情 <QQ号>")

    try:
        target_qq = int(arg)
    except ValueError:
        await emoji_cancel_cmd.finish("请输入有效的QQ号")

    group_id = event.group_id

    # 从自动贴表情列表中移除
    auto_emoji_users.discard((group_id, target_qq))
    logger.info(f"管理员取消了用户 {target_qq} 在群 {group_id} 的自动贴表情")
    await emoji_cancel_cmd.finish(f"已取消该用户的自动贴表情")


@group_emoji_cmd.handle()
async def handle_group_emoji(event: GroupMessageEvent):
    """处理全体贴表情命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await group_emoji_cmd.finish("权限不足，仅管理员可使用此命令")

    group_id = event.group_id

    # 添加到全体贴表情群列表
    auto_emoji_groups.add(group_id)
    logger.info(f"管理员开启了群 {group_id} 的全体贴表情功能")
    await group_emoji_cmd.finish(f"已开启全体贴表情，概率为 {config.group_emoji_chance * 100}%")


@group_emoji_cancel_cmd.handle()
async def handle_group_emoji_cancel(event: GroupMessageEvent):
    """处理取消全体贴表情命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await group_emoji_cancel_cmd.finish("权限不足，仅管理员可使用此命令")

    group_id = event.group_id

    # 从全体贴表情群列表中移除
    auto_emoji_groups.discard(group_id)
    logger.info(f"管理员取消了群 {group_id} 的全体贴表情功能")
    await group_emoji_cancel_cmd.finish(f"已取消全体贴表情")


@setkey_cmd.handle()
async def handle_setkey(event: MessageEvent, args: Message = CommandArg()):
    """处理关键词设置命令（仅管理员可用）"""
    config = get_plugin_config(Config)

    # 管理员权限校验
    if event.user_id != config.admin_qq:
        await setkey_cmd.finish("权限不足，仅管理员可使用此命令")

    arg = args.extract_plain_text().strip()

    if not arg:
        # 显示所有关键词
        keywords = db.get_all_keywords()
        if keywords:
            kw_list = "\n".join([f"{kw} -> {meaning}" for kw, meaning in keywords.items()])
            await setkey_cmd.finish(f"当前关键词映射:\n{kw_list}")
        else:
            await setkey_cmd.finish("当前没有关键词映射，使用 /setkey <关键词> <含义> 添加")

    # 解析参数：关键词 含义
    parts = arg.split(maxsplit=1)
    if len(parts) != 2:
        await setkey_cmd.finish("格式错误，请使用: /setkey <关键词> <含义>")

    keyword, meaning = parts
    db.add_keyword(keyword, meaning)
    await setkey_cmd.finish(f"已添加关键词映射: {keyword} -> {meaning}")


@settings_cmd.handle()
async def handle_settings(event: MessageEvent, args: Message = CommandArg()):
    """处理设置命令（仅管理员可用）"""
    config = get_plugin_config(Config)

    # 管理员权限校验
    if event.user_id != config.admin_qq:
        await settings_cmd.finish("权限不足，仅管理员可使用此命令")

    arg = args.extract_plain_text().strip()

    if not arg:
        # 显示当前白名单
        allowed_users = db.get_all_users()
        if allowed_users:
            user_list = "\n".join([str(uid) for uid in sorted(allowed_users)])
            await settings_cmd.finish(f"当前允许的用户:\n{user_list}")
        else:
            await settings_cmd.finish("当前没有允许的用户，使用 /settings <QQ号> 添加")

    # 解析 QQ 号
    try:
        qq_id = int(arg)
    except ValueError:
        await settings_cmd.finish("请输入有效的 QQ 号")

    # 添加或移除白名单
    if db.user_exists(qq_id):
        db.remove_user(qq_id)
        await settings_cmd.finish(f"已移除用户 {qq_id}")
    else:
        db.add_user(qq_id)
        await settings_cmd.finish(f"已添加用户 {qq_id}")


@groupsettings_cmd.handle()
async def handle_groupsettings(event: MessageEvent, args: Message = CommandArg()):
    """处理群设置命令（仅管理员可用）"""
    config = get_plugin_config(Config)

    # 管理员权限校验
    if event.user_id != config.admin_qq:
        await groupsettings_cmd.finish("权限不足，仅管理员可使用此命令")

    arg = args.extract_plain_text().strip()

    if not arg:
        # 显示当前群白名单
        allowed_groups = db.get_all_groups()
        if allowed_groups:
            group_list = "\n".join([str(gid) for gid in sorted(allowed_groups)])
            await groupsettings_cmd.finish(f"当前允许的群:\n{group_list}")
        else:
            await groupsettings_cmd.finish("当前没有允许的群，使用 /groupsettings <群号> 添加")

    # 解析群号
    try:
        group_id = int(arg)
    except ValueError:
        await groupsettings_cmd.finish("请输入有效的群号")

    # 添加或移除群白名单
    if db.group_exists(group_id):
        db.remove_group(group_id)
        await groupsettings_cmd.finish(f"已移除群 {group_id}")
    else:
        db.add_group(group_id)
        await groupsettings_cmd.finish(f"已添加群 {group_id}")

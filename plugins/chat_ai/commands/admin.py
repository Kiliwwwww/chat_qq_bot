import time

from nonebot import on_command, get_plugin_config, logger
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg

from ..config import Config
from .. import state
from ..state import db, auto_emoji_users, auto_emoji_groups, auto_emoji_all_groups_users, group_welcome_messages, ad_recall_groups

mute_cmd = on_command("闭嘴", priority=5, block=True)
emoji_cmd = on_command("贴表情", priority=5, block=True)
emoji_cancel_cmd = on_command("取消贴表情", priority=5, block=True)
group_emoji_cmd = on_command("全体贴表情", priority=5, block=True)
group_emoji_cancel_cmd = on_command("取消全体贴表情", priority=5, block=True)
emoji_all_cmd = on_command("贴表情all", priority=5, block=True)
emoji_all_cancel_cmd = on_command("取消贴表情all", priority=5, block=True)
setkey_cmd = on_command("setkey", aliases={"设置关键词"}, priority=5, block=True)
settings_cmd = on_command("settings", aliases={"设置"}, priority=5, block=True)
groupsettings_cmd = on_command("groupsettings", aliases={"群设置"}, priority=5, block=True)
welcome_cmd = on_command("欢迎语", priority=5, block=True)
ad_recall_on_cmd = on_command("开启群撤回", priority=5, block=True)
ad_recall_off_cmd = on_command("关闭群撤回", priority=5, block=True)
ad_keyword_cmd = on_command("广告词", priority=5, block=True)
ad_status_cmd = on_command("撤回状态", priority=5, block=True)


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
async def handle_group_emoji_cancel(event: MessageEvent):
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


@emoji_all_cmd.handle()
async def handle_emoji_all(event: MessageEvent, args: Message = CommandArg()):
    """处理全局贴表情命令（仅管理员可用，支持私聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await emoji_all_cmd.finish("权限不足，仅管理员可使用此命令")

    # 解析QQ号
    arg = args.extract_plain_text().strip()
    if not arg:
        await emoji_all_cmd.finish("请指定QQ号，格式：贴表情all <QQ号>")

    try:
        target_qq = int(arg)
    except ValueError:
        await emoji_all_cmd.finish("请输入有效的QQ号")

    # 添加到全局贴表情列表
    auto_emoji_all_groups_users.add(target_qq)
    logger.info(f"管理员设置了自动给用户 {target_qq} 在所有群贴表情")
    await emoji_all_cmd.finish(f"已开启自动给该用户在所有群贴🐒表情")


@emoji_all_cancel_cmd.handle()
async def handle_emoji_all_cancel(event: MessageEvent, args: Message = CommandArg()):
    """处理取消全局贴表情命令（仅管理员可用，支持私聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await emoji_all_cancel_cmd.finish("权限不足，仅管理员可使用此命令")

    # 解析QQ号
    arg = args.extract_plain_text().strip()
    if not arg:
        await emoji_all_cancel_cmd.finish("请指定QQ号，格式：取消贴表情all <QQ号>")

    try:
        target_qq = int(arg)
    except ValueError:
        await emoji_all_cancel_cmd.finish("请输入有效的QQ号")

    # 从全局贴表情列表中移除
    auto_emoji_all_groups_users.discard(target_qq)
    logger.info(f"管理员取消了用户 {target_qq} 在所有群的自动贴表情")
    await emoji_all_cancel_cmd.finish(f"已取消该用户在所有群的自动贴表情")


@setkey_cmd.handle()
async def handle_setkey(event: MessageEvent, args: Message = CommandArg()):
    """处理提示词设置命令（仅管理员可用）"""
    config = get_plugin_config(Config)

    # 管理员权限校验
    if event.user_id != config.admin_qq:
        await setkey_cmd.finish("权限不足，仅管理员可使用此命令")

    arg = args.extract_plain_text().strip()

    if not arg:
        # 显示所有提示词
        keywords = db.get_all_keywords()
        if keywords:
            kw_list = "\n".join([f"[{kw['id']}] {kw['content']}" for kw in keywords])
            await setkey_cmd.finish(f"当前提示词列表:\n{kw_list}")
        else:
            await setkey_cmd.finish("当前没有提示词，使用 /setkey <一句话> 添加")

    # 删除功能
    if arg.startswith("del "):
        try:
            keyword_id = int(arg[4:].strip())
        except ValueError:
            await setkey_cmd.finish("格式错误，请使用: /setkey del <ID>")

        if not db.keyword_id_exists(keyword_id):
            await setkey_cmd.finish(f"ID {keyword_id} 不存在")

        db.remove_keyword(keyword_id)
        await setkey_cmd.finish(f"已删除提示词 ID: {keyword_id}")

    # 添加提示词
    content = arg
    if db.keyword_exists(content):
        await setkey_cmd.finish("该提示词已存在")

    db.add_keyword(content)
    await setkey_cmd.finish(f"已添加提示词: {content}")


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


@welcome_cmd.handle()
async def handle_welcome(event: GroupMessageEvent, args: Message = CommandArg()):
    """处理欢迎语命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await welcome_cmd.finish("权限不足，仅管理员可使用此命令")

    group_id = event.group_id
    arg = args.extract_plain_text().strip()

    if not arg:
        # 显示当前群的欢迎语
        welcome_msg = db.get_welcome_message(group_id)
        if welcome_msg:
            await welcome_cmd.finish(f"当前群欢迎语:\n{welcome_msg}")
        else:
            await welcome_cmd.finish("当前群未设置欢迎语，使用 /欢迎语 <内容> 设置")

    # 设置欢迎语（同时更新数据库和内存）
    if db.set_welcome_message(group_id, arg):
        group_welcome_messages[group_id] = arg
        logger.info(f"管理员设置了群 {group_id} 的欢迎语: {arg}")
        await welcome_cmd.finish(f"已设置欢迎语: {arg}")
    else:
        await welcome_cmd.finish("设置欢迎语失败")


@ad_recall_on_cmd.handle()
async def handle_ad_recall_on(event: GroupMessageEvent):
    """处理开启群撤回命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await ad_recall_on_cmd.finish("权限不足，仅管理员可使用此命令")

    group_id = event.group_id

    # 添加到开启广告撤回的群集合
    ad_recall_groups.add(group_id)
    logger.info(f"管理员开启了群 {group_id} 的广告撤回功能")
    await ad_recall_on_cmd.finish("已开启群撤回，将自动撤回广告消息")


@ad_recall_off_cmd.handle()
async def handle_ad_recall_off(event: GroupMessageEvent):
    """处理关闭群撤回命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await ad_recall_off_cmd.finish("权限不足，仅管理员可使用此命令")

    group_id = event.group_id

    # 从开启广告撤回的群集合中移除
    ad_recall_groups.discard(group_id)
    logger.info(f"管理员关闭了群 {group_id} 的广告撤回功能")
    await ad_recall_off_cmd.finish("已关闭群撤回")


@ad_keyword_cmd.handle()
async def handle_ad_keyword(event: MessageEvent, args: Message = CommandArg()):
    """处理广告词命令（仅管理员可用）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await ad_keyword_cmd.finish("权限不足，仅管理员可使用此命令")

    arg = args.extract_plain_text().strip()

    if not arg:
        # 显示所有广告关键词
        keywords = db.get_all_ad_keywords()
        if keywords:
            kw_list = "\n".join([f"[{kw['id']}] {kw['keyword']}" for kw in keywords])
            await ad_keyword_cmd.finish(f"当前广告关键词列表:\n{kw_list}")
        else:
            await ad_keyword_cmd.finish("当前没有广告关键词，使用 /广告词 <关键词> 添加")

    # 删除功能
    if arg.startswith("del "):
        try:
            keyword_id = int(arg[4:].strip())
        except ValueError:
            await ad_keyword_cmd.finish("格式错误，请使用: /广告词 del <ID>")

        if db.remove_ad_keyword(keyword_id):
            await ad_keyword_cmd.finish(f"已删除广告关键词 ID: {keyword_id}")
        else:
            await ad_keyword_cmd.finish("删除失败")

    # 添加广告关键词
    if db.ad_keyword_exists(arg):
        await ad_keyword_cmd.finish("该广告关键词已存在")

    if db.add_ad_keyword(arg):
        await ad_keyword_cmd.finish(f"已添加广告关键词: {arg}")
    else:
        await ad_keyword_cmd.finish("添加失败")


@ad_status_cmd.handle()
async def handle_ad_status(event: GroupMessageEvent):
    """处理撤回状态命令（仅管理员可用，仅群聊）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await ad_status_cmd.finish("权限不足，仅管理员可使用此命令")

    group_id = event.group_id

    # 检查群是否开启了广告撤回
    is_enabled = group_id in ad_recall_groups

    # 获取广告关键词数量
    keywords = db.get_all_ad_keywords()
    keyword_count = len(keywords)

    status = "已开启" if is_enabled else "已关闭"
    await ad_status_cmd.finish(
        f"群撤回状态: {status}\n"
        f"广告关键词数量: {keyword_count}\n"
        f"当前开启撤回的群: {ad_recall_groups}"
    )

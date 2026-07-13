from pathlib import Path
import random
import time
from nonebot import on_command, on_message, get_plugin_config, require
from nonebot.adapters.onebot.v11 import MessageEvent, Message, MessageSegment, PrivateMessageEvent, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.exception import FinishedException
from nonebot import logger

from .config import Config
from .service import AIService
from .database import Database

# 依赖 localstore 插件
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

# 提示词文件路径
PROMPT_FILE = Path(__file__).parent.parent.parent / "data" / "md" / "system_prompt.md"
PROMPT_KIND_FILE = Path(__file__).parent.parent.parent / "data" / "md" / "system_prompt_kind.md"

# 当前提示词模式：default=默认（雌小鬼），kind=邻家大姐姐
current_prompt_mode: str = "default"

# 禁言状态：bot_mute_until 存储禁言到期时间戳
bot_mute_until: float = 0

# 需要自动贴表情的用户集合 {(group_id, user_id)}
auto_emoji_users: set[tuple[int, int]] = set()

# 开启全体贴表情的群集合 {group_id}
auto_emoji_groups: set[int] = set()

# 存储用户对话历史和AI服务实例
user_histories: dict[int, list[dict[str, str]]] = {}
group_histories: dict[int, list[dict[str, str]]] = {}
group_last_reply: dict[int, float] = {}  # 群最后回复时间戳
group_recent_messages: dict[int, list[tuple[int, str]]] = {}  # 群最近消息 [(user_id, message)]
group_last_repeated: dict[int, str] = {}  # 群最后复读的消息内容
ai_service: AIService = None

# 初始化数据库
db = Database(get_plugin_data_file("chat_ai.db"))


def init_ai_service():
    """初始化AI服务"""
    global ai_service, current_prompt_mode
    try:
        config = get_plugin_config(Config)
        # 从数据库读取人格模式
        current_prompt_mode = db.get_setting("prompt_mode", "default")
        # 根据当前模式选择提示词文件
        prompt_file = PROMPT_KIND_FILE if current_prompt_mode == "kind" else PROMPT_FILE
        system_prompt = AIService.load_prompt_from_file(prompt_file) or config.ai_system_prompt
        # 替换提示词中的管理员QQ号和昵称占位符
        if system_prompt:
            system_prompt = system_prompt.replace("{admin_qq}", str(config.admin_qq))
            system_prompt = system_prompt.replace("{admin_name}", config.admin_name)
        ai_service = AIService(
            api_key=config.ai_api_key,
            base_url=config.ai_base_url,
            model=config.ai_model,
            max_tokens=config.ai_max_tokens,
            temperature=config.ai_temperature,
            top_p=config.ai_top_p,
            system_prompt=system_prompt,
            debug_log=config.ai_debug_log,
        )
        logger.info(f"AI 服务初始化完成，当前人格模式: {current_prompt_mode}")
    except Exception as e:
        logger.error(f"AI 服务初始化失败: {e}")


def clean_history_images(messages: list[dict]) -> list[dict]:
    """清理历史记录中的图片，只保留最近3条消息的图片"""
    if not messages:
        return messages
    
    # 创建副本，避免修改原始数据
    cleaned = []
    for i, msg in enumerate(messages):
        # 只处理用户消息
        if msg["role"] == "user" and isinstance(msg["content"], list):
            # 最近3条消息保留图片，历史消息只保留文本
            if i >= len(messages) - 6:
                cleaned.append(msg)  # 最近6条消息完整保留
            else:
                # 历史消息只保留文本部分
                text_parts = [item for item in msg["content"] if item.get("type") == "text"]
                if text_parts:
                    cleaned.append({"role": "user", "content": text_parts})
                else:
                    # 如果没有文本部分，添加一个默认描述
                    cleaned.append({"role": "user", "content": "[图片消息]"})
        else:
            cleaned.append(msg)
    return cleaned


def get_keywords_prompt() -> str:
    """获取关键词映射提示词"""
    keywords = db.get_all_keywords()
    if not keywords:
        return ""
    kw_lines = "\n".join([f"- {kw}: {meaning}" for kw, meaning in keywords.items()])
    return f"\n\n用户自定义关键词映射:\n{kw_lines}"


def check_repeater(group_id: int, user_id: int, message: str) -> bool:
    """检测是否在复读，机器人跟读返回True"""
    if not message or len(message) > 100:  # 忽略空消息和过长消息
        return False
    
    if group_id not in group_recent_messages:
        group_recent_messages[group_id] = []
    
    recent = group_recent_messages[group_id]
    
    # 检查机器人是否已经复读过这条消息
    if group_id in group_last_repeated and group_last_repeated[group_id] == message:
        return False
    
    # 检查最近2条消息是否相同（连续复读），且来自不同用户
    if len(recent) >= 2:
        last1 = recent[-1]  # (user_id, message)
        last2 = recent[-2]  # (user_id, message)
        # 最近两条消息内容相同，且当前消息也相同，且来自不同用户
        if last1[1] == message and last2[1] == message and last1[0] != last2[0]:
            return True
    
    return False


def update_recent_messages(group_id: int, user_id: int, message: str):
    """更新群最近消息记录"""
    if not message or len(message) > 100:
        return
    
    if group_id not in group_recent_messages:
        group_recent_messages[group_id] = []
    
    recent = group_recent_messages[group_id]
    recent.append((user_id, message))
    
    # 只保留最近10条消息
    if len(recent) > 10:
        group_recent_messages[group_id] = recent[-10:]


# 注册命令处理器
reset_cmd = on_command("reset", aliases={"重置对话"}, priority=5, block=True)
settings_cmd = on_command("settings", aliases={"设置"}, priority=5, block=True)
groupsettings_cmd = on_command("groupsettings", aliases={"群设置"}, priority=5, block=True)
setkey_cmd = on_command("setkey", aliases={"设置关键词"}, priority=5, block=True)
help_cmd = on_command("help", aliases={"帮助"}, priority=5, block=True)
switch_kind_cmd = on_command("邻家大姐姐人格", priority=5, block=True)
switch_default_cmd = on_command("雌小鬼人格", priority=5, block=True)
mute_cmd = on_command("闭嘴", priority=5, block=True)
emoji_cmd = on_command("贴表情", priority=5, block=True)
emoji_cancel_cmd = on_command("取消贴表情", priority=5, block=True)
group_emoji_cmd = on_command("全体贴表情", priority=5, block=True)
group_emoji_cancel_cmd = on_command("取消全体贴表情", priority=5, block=True)

# 私聊消息处理器（优先级较低，在命令之后处理）
private_msg = on_message(priority=10, block=True)

# 群消息处理器
group_msg = on_message(priority=10, block=True)


@help_cmd.handle()
async def handle_help(event: MessageEvent):
    """显示帮助信息"""
    help_text = """可用命令：
/help 或 /帮助 - 显示此帮助
/reset 或 /重置对话 - 重置当前对话历史
/settings <QQ号> 或 /设置 - 管理用户白名单（管理员）
/groupsettings <群号> 或 /群设置 - 管理群白名单（管理员）
/setkey <关键词> <含义> 或 /设置关键词 - 设置关键词映射（管理员）
/邻家大姐姐人格 - 切换到邻家大姐姐人格
/雌小鬼人格 - 切换回默认人格
/贴表情 <QQ号> - 给指定用户消息贴随机表情（管理员）
/取消贴表情 <QQ号> - 取消给指定用户贴的表情（管理员）
/全体贴表情 - 给群内所有人消息随机贴表情（管理员）
/取消全体贴表情 - 取消全体贴表情（管理员）
/排行榜 或 /ranking - 查看群发言排行榜（管理员）
/weibo <UID> - 获取微博用户最新动态（私聊）
/sendweibo <UID> <群号> - 发送微博图片到指定群（私聊）"""
    await help_cmd.finish(help_text)


@switch_kind_cmd.handle()
async def handle_switch_kind(event: MessageEvent):
    """切换到邻家大姐姐人格"""
    global ai_service, current_prompt_mode
    
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await switch_kind_cmd.finish("权限不足，仅管理员可使用此命令")
    
    current_prompt_mode = "kind"
    db.set_setting("prompt_mode", "kind")
    ai_service = None  # 重置AI服务，下次使用时会重新初始化
    await switch_kind_cmd.finish("已切换到邻家大姐姐人格")


@switch_default_cmd.handle()
async def handle_switch_default(event: MessageEvent):
    """切换回默认人格（雌小鬼）"""
    global ai_service, current_prompt_mode
    
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await switch_default_cmd.finish("权限不足，仅管理员可使用此命令")
    
    current_prompt_mode = "default"
    db.set_setting("prompt_mode", "default")
    ai_service = None  # 重置AI服务，下次使用时会重新初始化
    await switch_default_cmd.finish("已切换回默认人格")


@mute_cmd.handle()
async def handle_mute(event: MessageEvent):
    """处理闭嘴命令（仅管理员可用）"""
    global bot_mute_until
    
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await mute_cmd.finish("权限不足，仅管理员可使用此命令")
    
    # 设置禁言5分钟
    bot_mute_until = time.time() + 300
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


@private_msg.handle()
async def handle_private_msg(event: MessageEvent):
    """处理私聊消息"""
    # 只处理私聊消息，群聊放行
    if not isinstance(event, PrivateMessageEvent):
        await private_msg.skip()

    # 非白名单用户放行
    if not db.user_exists(event.user_id):
        await private_msg.skip()

    if not ai_service:
        init_ai_service()

    # AI 服务未初始化放行
    if not ai_service:
        await private_msg.skip()

    # 检查是否在禁言期间
    if time.time() < bot_mute_until:
        await private_msg.skip()

    # 获取消息内容
    message = event.get_message()
    user_message = event.get_plaintext().strip()
    
    # 检查是否包含图片
    image_urls = []
    for segment in message:
        if segment.type == "image":
            image_url = segment.data.get("url", "")
            if image_url:
                image_urls.append(image_url)
    
    # 忽略空消息或命令（没有文本也没有图片）
    if (not user_message or user_message.startswith("/")) and not image_urls:
        await private_msg.skip()

    user_id = event.user_id

    # 获取用户历史记录
    if user_id not in user_histories:
        user_histories[user_id] = []

    # 构建用户消息内容
    if image_urls:
        # 有图片时，使用视觉API格式
        user_content = []
        if user_message:
            user_content.append({"type": "text", "text": user_message})
        for img_url in image_urls:
            try:
                # 使用图片外网地址
                user_content.append({"type": "image_url", "image_url": {"url": img_url}})
            except Exception as e:
                logger.error(f"图片处理失败: {e}")
                continue
        
        user_histories[user_id].append({
            "role": "user",
            "content": user_content,
        })
    else:
        # 纯文本消息
        user_histories[user_id].append({
            "role": "user",
            "content": user_message,
        })

    try:
        # 调用 AI 服务（带关键词提示词）
        keywords_prompt = get_keywords_prompt()
        system_prompt = ai_service.system_prompt + keywords_prompt if keywords_prompt else None
        # 清理历史记录中的图片，只保留最新消息的图片
        cleaned_history = clean_history_images(user_histories[user_id])
        reply = await ai_service.chat_with_history(
            messages=cleaned_history,
            system_prompt=system_prompt,
        )

        # 添加助手回复到历史
        user_histories[user_id].append({
            "role": "assistant",
            "content": reply,
        })

        # 限制历史记录长度（保留最近 10 轮对话）
        if len(user_histories[user_id]) > 20:
            user_histories[user_id] = user_histories[user_id][-20:]

        logger.info(f"私聊回复 用户:{user_id} 回复:{reply}")
        await private_msg.finish(reply)

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # 高风险拦截兜底回复
        if "high risk" in str(e).lower():
            await private_msg.finish("别发些乱七八糟的东西！")
        await private_msg.finish(f"AI 调用失败: {e}")


@group_msg.handle()
async def handle_group_msg(event: MessageEvent):
    """处理群消息"""
    # 只处理群消息
    if not isinstance(event, GroupMessageEvent):
        await group_msg.skip()

    config = get_plugin_config(Config)
    group_id = event.group_id

    # 自动贴表情功能（不受群白名单限制）
    if (group_id, event.user_id) in auto_emoji_users:
        try:
            from nonebot import get_bot
            bot = get_bot()
            # 随机表情ID列表
            emoji_ids = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
            random_emoji = random.choice(emoji_ids)
            await bot.set_msg_emoji_like(message_id=event.message_id, emoji_id=random_emoji)
            logger.info(f"自动给用户 {event.user_id} 在群 {group_id} 的消息贴了表情 {random_emoji}")
        except Exception as e:
            logger.error(f"自动贴表情失败: {e}")

    # 全体贴表情功能（按概率给群内所有人贴表情，不受群白名单限制）
    if group_id in auto_emoji_groups:
        config_emoji = get_plugin_config(Config)
        if random.random() < config_emoji.group_emoji_chance:
            try:
                from nonebot import get_bot
                bot = get_bot()
                emoji_ids = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
                random_emoji = random.choice(emoji_ids)
                await bot.set_msg_emoji_like(message_id=event.message_id, emoji_id=random_emoji)
                logger.info(f"全体贴表情：给用户 {event.user_id} 在群 {group_id} 的消息贴了表情 {random_emoji}")
            except Exception as e:
                logger.error(f"全体贴表情失败: {e}")

    # 群白名单检查
    if not db.group_exists(group_id):
        await group_msg.skip()

    # 获取消息内容
    message = event.get_message()
    user_message = event.get_plaintext().strip()
    
    # 检查是否包含图片
    image_urls = []
    for segment in message:
        if segment.type == "image":
            image_url = segment.data.get("url", "")
            if image_url:
                image_urls.append(image_url)
    
    # 忽略空消息或命令
    if (not user_message or user_message.startswith("/")) and not image_urls:
        await group_msg.skip()

    # 检查是否在禁言期间
    if time.time() < bot_mute_until:
        await group_msg.skip()

    # @机器人且包含"妈妈"时回复"叫妈妈"
    if event.is_tome() and "妈妈" in user_message:
        reply_msg = MessageSegment.reply(event.message_id) + "叫妈妈"
        logger.info(f"妈妈触发 群:{group_id} 用户:{event.user_id}")
        await group_msg.finish(reply_msg)

    # 复读检测：如果群里有人在复读，机器人也跟着复读（不受冷却和概率限制）
    if user_message and not image_urls and check_repeater(group_id, event.user_id, user_message):
        update_recent_messages(group_id, event.user_id, user_message)
        group_last_reply[group_id] = time.time()
        group_last_repeated[group_id] = user_message  # 记录机器人的最后复读消息
        logger.info(f"复读消息 群:{group_id} 消息:{user_message}")
        await group_msg.finish(user_message)

    # 随机复读群友消息（文本或图片）
    if random.random() < config.random_repeat_chance:
        update_recent_messages(group_id, event.user_id, user_message)
        group_last_reply[group_id] = time.time()
        logger.info(f"随机复读 群:{group_id} 消息:{user_message[:20] if user_message else '图片'}")
        # 构建复读消息
        repeat_msg = Message()
        if user_message:
            repeat_msg += MessageSegment.text(user_message)
        for segment in message:
            if segment.type == "image":
                repeat_msg += MessageSegment.image(segment.data.get("file", ""))
        if repeat_msg:
            await group_msg.finish(repeat_msg)

    # 更新最近消息记录
    update_recent_messages(group_id, event.user_id, user_message)

    # 获取群对话历史
    if group_id not in group_histories:
        group_histories[group_id] = []

    # 获取发言人昵称（优先群名片，其次QQ昵称）
    sender_name = event.sender.card or event.sender.nickname or str(event.user_id)
    user_id = event.user_id

    # 将所有用户消息加入历史（不管AI是否回复）
    if image_urls:
        user_content = []
        text_with_name = f"[{sender_name}][{user_id}] {user_message}" if user_message else f"[{sender_name}][{user_id}] 发送了一张图片"
        user_content.append({"type": "text", "text": text_with_name})
        for img_url in image_urls:
            try:
                # 使用图片外网地址
                user_content.append({"type": "image_url", "image_url": {"url": img_url}})
            except Exception as e:
                logger.error(f"图片处理失败: {e}")
                continue
        
        group_histories[group_id].append({
            "role": "user",
            "content": user_content,
        })
    else:
        group_histories[group_id].append({
            "role": "user",
            "content": f"[{sender_name}][{user_id}] {user_message}",
        })

    # 限制历史记录长度
    if len(group_histories[group_id]) > 20:
        group_histories[group_id] = group_histories[group_id][-20:]

    # 判断是否被@：被@则立即回复，不受概率和冷却限制
    is_at_me = event.is_tome()

    # 冷却检查：防止短时间内重复回复同一群（被@时跳过冷却检查）
    current_time = time.time()
    if not is_at_me and group_id in group_last_reply and current_time - group_last_reply[group_id] < 3:
        await group_msg.skip()

    # 未被@时，进行概率检查
    if not is_at_me and random.random() > config.group_reply_chance:
        await group_msg.skip()

    if not ai_service:
        init_ai_service()

    if not ai_service:
        await group_msg.skip()

    try:
        # 调用 AI 服务（带关键词提示词）
        keywords_prompt = get_keywords_prompt()
        # 管理员艾特时启用女仆模式
        admin_maid_prompt = ""
        if is_at_me and event.user_id == config.admin_qq:
            admin_maid_prompt = "\n\n当前是主人在艾特你，请切换成女仆模式，用恭敬、温柔、撒娇的语气回复主人。"
        system_prompt = ai_service.system_prompt + keywords_prompt + admin_maid_prompt if (keywords_prompt or admin_maid_prompt) else None
        # 清理历史记录中的图片，只保留最新消息的图片
        cleaned_history = clean_history_images(group_histories[group_id])
        reply = await ai_service.chat_with_history(
            messages=cleaned_history,
            system_prompt=system_prompt,
        )

        group_histories[group_id].append({
            "role": "assistant",
            "content": reply,
        })

        # 限制历史记录长度
        if len(group_histories[group_id]) > 20:
            group_histories[group_id] = group_histories[group_id][-20:]

        # 更新最后回复时间戳
        group_last_reply[group_id] = time.time()
        logger.info(f"群消息已回复 群:{group_id} 消息:{user_message[:20]}... 回复:{reply}")
        
        # 被@时回复原消息
        if is_at_me:
            await group_msg.finish(MessageSegment.reply(event.message_id) + reply)
        else:
            await group_msg.finish(reply)

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"群消息 AI 调用失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # 更新最后回复时间戳
        group_last_reply[group_id] = time.time()
        # 高风险内容拦截
        if "high risk" in str(e).lower():
            await group_msg.finish("别发些奇奇怪怪的东西！")
        # 其他失败情况静默处理，不回复群消息


@reset_cmd.handle()
async def handle_reset(event: MessageEvent):
    """重置对话历史"""
    user_id = event.user_id
    reset_anything = False

    # 重置用户私聊历史
    if user_id in user_histories:
        del user_histories[user_id]
        reset_anything = True

    # 如果是群消息，同时重置群对话历史
    if isinstance(event, GroupMessageEvent):
        group_id = event.group_id
        if group_id in group_histories:
            del group_histories[group_id]
            reset_anything = True

    if reset_anything:
        await reset_cmd.finish("对话历史已重置")
    else:
        await reset_cmd.finish("没有对话历史需要重置")

import random
import time
import json

from nonebot import on_command, on_message, on_notice, get_plugin_config, logger
from nonebot.adapters.onebot.v11 import (
    MessageEvent,
    Message,
    MessageSegment,
    GroupMessageEvent,
    GroupIncreaseNoticeEvent,
)
from nonebot.exception import FinishedException

from ..config import Config
from .. import state
from ..state import (
    db,
    group_histories,
    group_last_reply,
    group_last_repeated,
    group_welcome_messages,
    auto_emoji_users,
    auto_emoji_groups,
    auto_emoji_all_groups_users,
    ad_recall_groups,
    init_ai_service,
    get_group_history,
    set_group_history,
    delete_group_history,
    delete_user_history,
    AD_DETECTION_PROMPT_FILE,
)
from ..utils.helpers import (
    clean_history_images,
    get_keywords_prompt,
    check_repeater,
    update_recent_messages,
)

reset_cmd = on_command("reset", aliases={"重置对话"}, priority=5, block=True)

# 群消息处理器
group_msg = on_message(priority=10, block=True)

# 群成员加入事件处理器
member_join = on_notice()


@reset_cmd.handle()
async def handle_reset(event: MessageEvent):
    """重置对话历史"""
    user_id = event.user_id
    reset_anything = False

    # 重置用户私聊历史
    await delete_user_history(user_id)
    reset_anything = True

    # 如果是群消息，同时重置群对话历史
    if isinstance(event, GroupMessageEvent):
        group_id = event.group_id
        await delete_group_history(group_id)
        reset_anything = True

    if reset_anything:
        await reset_cmd.finish("对话历史已重置")
    else:
        await reset_cmd.finish("没有对话历史需要重置")


def check_ad_keywords(message: str) -> bool:
    """检查消息是否包含广告关键词"""
    keywords = db.get_all_ad_keywords()
    if not keywords:
        return False
    for kw in keywords:
        if kw["keyword"] in message:
            return True
    return False


async def check_ad_by_ai(message: str) -> bool:
    """使用大模型判断消息是否为广告"""
    try:
        if not state.ai_service:
            init_ai_service()
        if not state.ai_service:
            return False

        # 加载广告检测提示词
        prompt = ""
        if AD_DETECTION_PROMPT_FILE.exists():
            prompt = AD_DETECTION_PROMPT_FILE.read_text(encoding="utf-8").strip()

        if not prompt:
            return False

        # 调用大模型判断
        full_prompt = prompt + message
        response = await state.ai_service.chat(
            user_message=full_prompt,
            system_prompt="你是一个广告内容检测助手，请严格按照要求的JSON格式返回结果。",
        )

        # 解析返回的JSON
        response = response.strip()
        # 尝试提取JSON部分
        if "{" in response and "}" in response:
            json_str = response[response.index("{"):response.rindex("}") + 1]
            result = json.loads(json_str)
            return result.get("is_ad", False)

        return False
    except Exception as e:
        logger.error(f"AI广告检测失败: {e}")
        return False


async def handle_ad_recall(bot, event: GroupMessageEvent):
    """处理广告撤回逻辑"""
    group_id = event.group_id
    user_message = event.get_plaintext().strip()

    # 检查群是否开启了广告撤回
    if group_id not in ad_recall_groups:
        return False

    logger.info(f"广告检测: 群:{group_id} 用户:{event.user_id} 消息长度:{len(user_message)} 内容:{user_message[:50]}")

    # 低于5个字不处理
    if len(user_message) < 5:
        logger.info(f"广告检测: 消息低于5个字，跳过")
        return False

    is_ad = False

    # 首先检查广告关键词
    if check_ad_keywords(user_message):
        is_ad = True
        logger.info(f"广告关键词命中 群:{group_id} 用户:{event.user_id} 消息:{user_message[:30]}")

    # 超过50个字且未命中关键词，使用大模型判断
    elif len(user_message) > 50:
        logger.info(f"广告检测: 消息超过50个字，调用AI判断")
        is_ad = await check_ad_by_ai(user_message)
        if is_ad:
            logger.info(f"AI判定为广告 群:{group_id} 用户:{event.user_id} 消息:{user_message[:30]}")

    # 如果是广告，撤回消息
    if is_ad:
        try:
            await bot.delete_msg(message_id=event.message_id)
            logger.info(f"已撤回广告消息 群:{group_id} 用户:{event.user_id} message_id:{event.message_id}")
            return True
        except Exception as e:
            logger.error(f"撤回消息失败: {e}")

    return False


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
            emoji_ids = list(range(9, 101))
            random_emoji = random.choice(emoji_ids)
            await bot.set_msg_emoji_like(message_id=event.message_id, emoji_id=random_emoji)
            logger.info(f"自动给用户 {event.user_id} 在群 {group_id} 的消息贴了表情 {random_emoji}")
        except Exception as e:
            logger.error(f"自动贴表情失败: {e}")

    # 全局贴表情功能（给指定用户在所有群贴表情）
    if event.user_id in auto_emoji_all_groups_users:
        try:
            from nonebot import get_bot
            bot = get_bot()
            emoji_id = config.global_emoji_id
            await bot.set_msg_emoji_like(message_id=event.message_id, emoji_id=emoji_id)
            logger.info(f"全局贴表情：给用户 {event.user_id} 在群 {group_id} 的消息贴了表情 {emoji_id}")
        except Exception as e:
            logger.error(f"全局贴表情失败: {e}")

    # 全体贴表情功能（按概率给群内所有人贴表情，不受群白名单限制）
    if group_id in auto_emoji_groups:
        config_emoji = get_plugin_config(Config)
        if random.random() < config_emoji.group_emoji_chance:
            try:
                from nonebot import get_bot
                bot = get_bot()
                emoji_ids = list(range(9, 101))
                random_emoji = random.choice(emoji_ids)
                await bot.set_msg_emoji_like(message_id=event.message_id, emoji_id=random_emoji)
                logger.info(f"全体贴表情：给用户 {event.user_id} 在群 {group_id} 的消息贴了表情 {random_emoji}")
            except Exception as e:
                logger.error(f"全体贴表情失败: {e}")

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

    # 广告检测和撤回（在忽略空消息之前执行）
    from nonebot import get_bot
    bot = get_bot()
    if await handle_ad_recall(bot, event):
        await group_msg.finish()

    # 忽略空消息或命令
    if (not user_message or user_message.startswith("/")) and not image_urls:
        await group_msg.skip()

    # 获取群对话历史（从 Redis）
    history = await get_group_history(group_id)

    # 保存原始历史记录副本，用于 AI 调用失败时回滚
    original_history = list(history)

    # 获取发言人昵称（优先群名片，其次QQ昵称）
    sender_name = event.sender.card or event.sender.nickname or str(event.user_id)
    user_id = event.user_id

    # 将用户消息加入历史（不管是否触发AI回复）
    if image_urls:
        user_content = []
        text_with_name = f"[{sender_name}][{user_id}] {user_message}" if user_message else f"[{sender_name}][{user_id}] 发送了一张图片"
        user_content.append({"type": "text", "text": text_with_name})
        for img_url in image_urls:
            try:
                user_content.append({"type": "image_url", "image_url": {"url": img_url}})
            except Exception as e:
                logger.error(f"图片处理失败: {e}")
                continue
        history.append({
            "role": "user",
            "content": user_content,
        })
    else:
        history.append({
            "role": "user",
            "content": f"[{sender_name}][{user_id}] {user_message}",
        })

    # 限制历史记录长度
    if len(history) > config.ai_context_limit:
        history = history[-config.ai_context_limit:]

    # 立即保存到 Redis
    await set_group_history(group_id, history)

    # 更新最近消息记录（用于复读检测）
    update_recent_messages(group_id, event.user_id, user_message)

    # 群白名单检查（仅控制AI回复，不影响消息存储）
    if not db.group_exists(group_id):
        await group_msg.skip()

    # 检查是否在禁言期间
    if time.time() < state.bot_mute_until:
        await group_msg.skip()

    # @机器人且包含"妈妈"时回复"叫妈妈"
    if event.is_tome() and "妈妈" in user_message:
        reply_msg = MessageSegment.reply(event.message_id) + "叫妈妈"
        logger.info(f"妈妈触发 群:{group_id} 用户:{event.user_id}")
        await group_msg.finish(reply_msg)

    # 复读检测：如果群里有人在复读，机器人也跟着复读（不受冷却和概率限制）
    if user_message and not image_urls and check_repeater(group_id, event.user_id, user_message):
        group_last_reply[group_id] = time.time()
        group_last_repeated[group_id] = user_message  # 记录机器人的最后复读消息
        logger.info(f"复读消息 群:{group_id} 消息:{user_message}")
        await group_msg.finish(user_message)

    # 随机复读群友消息（文本或图片）
    if random.random() < config.random_repeat_chance:
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

    # 判断是否被@：被@则立即回复，不受概率和冷却限制
    is_at_me = event.is_tome()

    # 冷却检查：防止短时间内重复回复同一群（被@时跳过冷却检查）
    current_time = time.time()
    if not is_at_me and group_id in group_last_reply and current_time - group_last_reply[group_id] < 3:
        await group_msg.skip()

    # 未被@时，进行概率检查
    if not is_at_me and random.random() > config.group_reply_chance:
        await group_msg.skip()

    if not state.ai_service:
        init_ai_service()

    if not state.ai_service:
        await group_msg.skip()

    try:
        # 调用 AI 服务（带关键词提示词）
        keywords_prompt = get_keywords_prompt()
        # 管理员艾特时启用女仆模式
        admin_maid_prompt = ""
        if is_at_me and event.user_id == config.admin_qq:
            admin_maid_prompt = "\n\n当前是主人在艾特你，请切换成女仆模式，用恭敬、温柔、撒娇的语气回复主人。"
        system_prompt = state.ai_service.system_prompt + keywords_prompt + admin_maid_prompt if (keywords_prompt or admin_maid_prompt) else None

        # RAGFlow 知识库检索
        rag_message = None
        if state.ragflow_client and user_message:
            rag_result = await state.ragflow_client.retrieve(user_message)
            rag_message = state.ragflow_client.build_context_message(rag_result)

        # 清理历史记录中的图片，只保留最新消息的图片
        cleaned_history = clean_history_images(history)
        reply = await state.ai_service.chat_with_history(
            messages=cleaned_history,
            system_prompt=system_prompt,
            rag_message=rag_message,
        )

        history.append({
            "role": "assistant",
            "content": reply,
        })

        # 限制历史记录长度
        if len(history) > config.ai_context_limit:
            history = history[-config.ai_context_limit:]
        
        # 保存到 Redis
        await set_group_history(group_id, history)

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
        # AI 调用失败，回滚历史记录（移除本次用户消息，避免孤立消息污染上下文）
        await set_group_history(group_id, original_history)
        # 更新最后回复时间戳
        group_last_reply[group_id] = time.time()
        # 高风险内容拦截
        if "high risk" in str(e).lower():
            await group_msg.finish("别发些奇奇怪怪的东西！")
        # 其他失败情况静默处理，不回复群消息


@member_join.handle()
async def handle_member_join(event: GroupIncreaseNoticeEvent):
    """处理群成员加入事件"""
    group_id = event.group_id
    user_id = event.user_id

    # 检查群是否设置了欢迎语
    if group_id in group_welcome_messages:
        welcome_msg = group_welcome_messages[group_id]
        # @新成员并发送欢迎语
        reply_msg = MessageSegment.at(user_id) + " " + welcome_msg
        logger.info(f"群 {group_id} 有新成员 {user_id} 加入，发送欢迎语")
        await member_join.finish(reply_msg)

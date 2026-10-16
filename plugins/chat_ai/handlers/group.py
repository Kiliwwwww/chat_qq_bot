import random
import time
import json
import asyncio
import base64
from datetime import datetime

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
    group_last_activity,
    group_welcome_messages,
    auto_emoji_users,
    auto_emoji_groups,
    auto_emoji_all_groups_users,
    ad_recall_groups,
    kb_groups,
    CHAT_LOG_DIR,
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
    get_time_hint,
    NO_META_RULE,
    MULTI_MESSAGE_HINT,
    FORCE_MULTI_HINT,
    should_force_multi_message,
    is_meta_decline,
    check_repeater,
    update_recent_messages,
    mark_bot_talked,
    clear_bot_talked,
    check_follow_up,
)
from ..utils.tts import synthesize
from ..utils.forward import extract_forward_text
# 奶龙表情包（本地表情库 + 群开关），详见 plugins/meme_sync
from plugins.meme_sync import meme_library

reset_cmd = on_command("reset", aliases={"重置对话"}, priority=5, block=True)


def save_chat_log(group_id: int, sender_name: str, user_id: int, message: str) -> None:
    """保存群聊天记录到文件"""
    if group_id not in kb_groups:
        return
    if not message:
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = CHAT_LOG_DIR / f"{group_id}_{date_str}.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}][{sender_name}][{user_id}] {message}\n"

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.error(f"保存聊天记录失败: {e}")

# 群消息处理器
group_msg = on_message(priority=10, block=True)

# 群成员加入事件处理器
member_join = on_notice()


@reset_cmd.handle()
async def handle_reset(event: MessageEvent):
    """重置对话历史（仅管理员可用）"""
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        return

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
    need_ai_check = False

    # 首先检查广告关键词
    if check_ad_keywords(user_message):
        need_ai_check = True
        logger.info(f"广告关键词命中 群:{group_id} 用户:{event.user_id} 消息:{user_message[:30]}")

    # 超过50个字且未命中关键词，也需要AI判断
    elif len(user_message) > 50:
        need_ai_check = True
        logger.info(f"广告检测: 消息超过50个字，调用AI判断")

    # 需要AI判断时，调用大模型（带30秒超时）
    if need_ai_check:
        try:
            is_ad = await asyncio.wait_for(check_ad_by_ai(user_message), timeout=30)
            if is_ad:
                logger.info(f"AI判定为广告 群:{group_id} 用户:{event.user_id} 消息:{user_message[:30]}")
            else:
                logger.info(f"AI判定为非广告 群:{group_id} 用户:{event.user_id} 消息:{user_message[:30]}")
        except asyncio.TimeoutError:
            logger.warning(f"AI广告检测超时(30秒)，默认判定为广告 群:{group_id} 用户:{event.user_id} 消息:{user_message[:30]}")
            is_ad = True
        except Exception as e:
            logger.error(f"AI广告检测异常: {e}，默认判定为广告 群:{group_id} 用户:{event.user_id}")
            is_ad = True

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

    # 解析合并转发（聊天记录）消息
    try:
        forwarder = event.sender.card or event.sender.nickname or str(event.user_id)
        forward_text = await extract_forward_text(message, forwarder=forwarder)
        if forward_text:
            user_message = (user_message + "\n" if user_message else "") + forward_text
    except Exception as e:
        logger.warning(f"解析合并转发消息失败: {e}")

    # 保存聊天记录到文件（仅对开启知识库的群）
    sender_name = event.sender.card or event.sender.nickname or str(event.user_id)
    if user_message:
        save_chat_log(group_id, sender_name, event.user_id, user_message)

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

    # 检测是否@了机器人，用于标记消息
    is_at_me = event.is_tome()

    # 对话延续：机器人刚说完话，它搭话的那个人紧接着回了一句（没被群里其他人插话打断）
    # 这种"顺口接话"不@也算是在跟机器人说话，不用逼着群友每次都@一次
    follow_up = (
        config.group_follow_up_enabled
        and not is_at_me
        and check_follow_up(group_id, user_id, config.group_follow_up_window)
    )

    # 将用户消息加入历史（不管是否触发AI回复）
    # 在消息里标明这条是不是冲着机器人来的，让AI知道该不该接
    if is_at_me:
        at_prefix = "[@我] "
    elif follow_up:
        at_prefix = "[接着我说话] "
    else:
        at_prefix = ""
    if image_urls:
        user_content = []
        text_with_name = f"[{sender_name}][{user_id}] {at_prefix}{user_message}" if user_message else f"[{sender_name}][{user_id}] 发送了一张图片"
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
            "content": f"[{sender_name}][{user_id}] {at_prefix}{user_message}",
        })

    # 限制历史记录长度
    if len(history) > config.ai_context_limit:
        history = history[-config.ai_context_limit:]

    # 立即保存到 Redis
    await set_group_history(group_id, history)

    # 更新最近消息记录（用于复读检测）
    update_recent_messages(group_id, event.user_id, user_message)

    # 记录群最后活跃时间（用于主动冒泡判断）
    group_last_activity[group_id] = time.time()

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

    # 关键词强制连发：仅作为"已决定回复"之后的增强，不单独召唤机器人
    force_trigger = (
        config.multi_message_enabled
        and config.multi_message_force_enabled
        and should_force_multi_message(user_message)
    )

    # 冷却检查：防止短时间内重复回复同一群（被@或接着我说话时跳过冷却检查）
    current_time = time.time()
    if (
        not is_at_me
        and not follow_up
        and group_id in group_last_reply
        and current_time - group_last_reply[group_id] < 3
    ):
        await group_msg.skip()

    # 未被@也没接着我说话时，进行概率检查
    if not is_at_me and not follow_up and random.random() > config.group_reply_chance:
        await group_msg.skip()

    # 接话单独用一套概率（默认 1.0：既然在跟机器人聊，就接住，别晾着）
    if follow_up and random.random() > config.group_follow_up_chance:
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
        # 时间感知提示词
        time_prompt = get_time_hint()
        system_prompt = (
            state.ai_service.system_prompt + keywords_prompt + admin_maid_prompt
            + time_prompt + NO_META_RULE
        )
        if config.multi_message_enabled:
            system_prompt += MULTI_MESSAGE_HINT

        # 关键词强制连发：计算本轮目标条数
        force_target = 0
        if force_trigger:
            force_target = random.randint(
                min(config.multi_message_force_min, config.multi_message_force_max),
                max(config.multi_message_force_min, config.multi_message_force_max),
            )
            force_target = max(2, min(force_target, config.multi_message_max))
            system_prompt += FORCE_MULTI_HINT.format(n=max(1, force_target - 1))
            logger.info(f"关键词触发强制连发 群:{group_id} 目标条数:{force_target}")

        # 历史记录中的图片默认保留（最近 ai_context_limit 条里的图都会发给 AI），
        # 需要退回旧的"只保留最新一条消息的图片"行为时把开关打开
        if config.history_image_clean_enabled:
            request_history = clean_history_images(history)
        else:
            request_history = history

        # RAGFlow 检索 + 联网搜索 + 语音 + 连发消息（由 AI 自主决定）
        # 群聊使用群绑定的知识库，不使用全局配置
        group_kb_id = state.kb_groups.get(group_id)
        group_kb_ids = [group_kb_id] if group_kb_id else None
        result = await state.ai_service.chat_with_tools(
            messages=request_history,
            system_prompt=system_prompt,
            rag_client=state.ragflow_client if user_message else None,
            allow_voice=config.tts_enabled and not force_trigger,
            allow_followup=config.multi_message_enabled,
            force_followup=force_target,
            kb_ids=group_kb_ids,
            web_search_client=state.web_search_client if user_message else None,
        )

        # AI 决定用语音回复：只发语音，不引用群友消息
        if result.has_voice:
            history.append({
                "role": "assistant",
                "content": result.voice_text,
            })
            if len(history) > config.ai_context_limit:
                history = history[-config.ai_context_limit:]
            await set_group_history(group_id, history)
            group_last_reply[group_id] = time.time()
            # 语音也是一次搭话，之后对方顺口接话同样算延续
            mark_bot_talked(group_id, user_id)
            try:
                audio = await synthesize(
                    result.voice_text,
                    result.voice_instruct or config.tts_instruct,
                )
            except Exception as e:
                logger.error(f"语音生成失败，改为不发 群:{group_id}: {e}")
                await group_msg.finish()
            logger.info(f"AI 语音回复 群:{group_id} 内容:{result.voice_text[:20]}...")
            record = MessageSegment.record(f"base64://{base64.b64encode(audio).decode()}")
            await group_msg.finish(record)

        reply = result.text

        # 连发消息：正文之外，AI 可主动补发若干条（过滤空内容和判断性回复）
        extra_messages: list[str] = []
        if config.multi_message_enabled:
            for extra in result.followups:
                extra = (extra or "").strip()
                if not extra or is_meta_decline(extra):
                    continue
                extra_messages.append(extra)
            # 单轮总条数上限（含主回复）
            extra_messages = extra_messages[: max(0, config.multi_message_max - 1)]

        # 空回复兜底：不发送、不写入历史（MiMo 偶发返回空内容）
        if (not reply or not reply.strip()) and not extra_messages:
            logger.warning(f"AI 返回空回复，静默跳过 群:{group_id}")
            group_last_reply[group_id] = time.time()
            # 这轮没说话，对话延续的窗口就此关掉，别让后续消息反复触发
            clear_bot_talked(group_id)
            await group_msg.finish()

        # 拦截 AI 泄露的判断性回复（如"不用回复，跟我没关系"），静默不发送
        if reply and is_meta_decline(reply):
            logger.info(f"AI 输出判断性回复，已拦截不发送 群:{group_id} 回复:{reply}")
            reply = ""

        # 组装本轮要发送的所有消息
        messages_to_send = ([reply.strip()] if reply and reply.strip() else []) + extra_messages
        if not messages_to_send:
            logger.warning(f"AI 回复全部无效，静默跳过 群:{group_id}")
            group_last_reply[group_id] = time.time()
            clear_bot_talked(group_id)
            await group_msg.finish()

        # 逐条写入历史
        for m in messages_to_send:
            history.append({
                "role": "assistant",
                "content": m,
            })

        # 限制历史记录长度
        if len(history) > config.ai_context_limit:
            history = history[-config.ai_context_limit:]
        
        # 保存到 Redis
        await set_group_history(group_id, history)

        # 更新最后回复时间戳
        group_last_reply[group_id] = time.time()
        # 记住这次搭话的对象：对方紧接着顺口接话时，不必再@一次
        mark_bot_talked(group_id, user_id)
        logger.info(
            f"群消息已回复 群:{group_id} 消息:{user_message[:20]}... "
            f"共 {len(messages_to_send)} 条 回复:{messages_to_send}"
        )

        # 奶龙表情包：开启了该功能的群里，回复结束后会再单独跟一条图片消息
        meme_on = meme_library.is_group_enabled(group_id)

        # 被@时第一条引用原消息，其余作为连续补发的消息
        first_reply = messages_to_send[0]
        first_msg = Message(first_reply)
        if is_at_me:
            first_msg = MessageSegment.reply(event.message_id) + first_msg
        await group_msg.send(first_msg)
        for extra in messages_to_send[1:]:
            await asyncio.sleep(random.uniform(0.6, 1.4))
            await group_msg.send(extra)

        # 回复结束后单独跟一条图片消息（与回复是两条独立消息，不引用任何人）
        if meme_on and random.random() < meme_library.reply_meme_chance():
            picked = await meme_library.random_image_segment()
            if picked is not None:
                meme_seg, meme_name = picked
                await asyncio.sleep(random.uniform(0.8, 1.6))
                try:
                    await group_msg.send(meme_seg)
                except Exception as exc:
                    logger.warning(f"发送表情包失败 群:{group_id} 图片:{meme_name} 原因:{exc}")
                else:
                    logger.info(f"回复后发送表情包 群:{group_id} 图片:{meme_name}")
        await group_msg.finish()

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
        # 这轮没回出去，关掉对话延续窗口，避免后续消息反复触发失败的调用
        clear_bot_talked(group_id)
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

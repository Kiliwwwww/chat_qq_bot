import time
import base64

from nonebot import on_message, get_plugin_config, logger
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, PrivateMessageEvent
from nonebot.exception import FinishedException

from ..config import Config
from .. import state
from ..state import db, user_histories, init_ai_service, get_user_history, set_user_history
from ..utils.helpers import clean_history_images, get_keywords_prompt, get_time_hint
from ..utils.tts import synthesize

# 私聊消息处理器（优先级较低，在命令之后处理）
private_msg = on_message(priority=10, block=True)


@private_msg.handle()
async def handle_private_msg(event: MessageEvent):
    """处理私聊消息"""
    # 只处理私聊消息，群聊放行
    if not isinstance(event, PrivateMessageEvent):
        await private_msg.skip()

    config = get_plugin_config(Config)
    
    # 非白名单用户放行
    if not db.user_exists(event.user_id):
        await private_msg.skip()

    if not state.ai_service:
        init_ai_service()

    # AI 服务未初始化放行
    if not state.ai_service:
        await private_msg.skip()

    # 检查是否在禁言期间
    if time.time() < state.bot_mute_until:
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

    # 获取用户历史记录（从 Redis）
    history = await get_user_history(user_id)

    # 保存原始历史记录副本，用于 AI 调用失败时回滚
    original_history = list(history)

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

        history.append({
            "role": "user",
            "content": user_content,
        })
    else:
        # 纯文本消息
        history.append({
            "role": "user",
            "content": user_message,
        })

    # 限制历史记录长度
    if len(history) > config.ai_context_limit:
        history = history[-config.ai_context_limit:]

    # 用户消息立即缓存到 Redis
    await set_user_history(user_id, history)

    try:
        # 调用 AI 服务（带关键词提示词 + 时间感知）
        keywords_prompt = get_keywords_prompt()
        time_prompt = get_time_hint()
        system_prompt = state.ai_service.system_prompt + keywords_prompt + time_prompt

        # 清理历史记录中的图片，只保留最新消息的图片
        cleaned_history = clean_history_images(history)

        # RAGFlow 检索 + 语音工具（AI 自主决定是否检索、是否用语音回复）
        result = await state.ai_service.chat_with_tools(
            messages=cleaned_history,
            system_prompt=system_prompt,
            rag_client=state.ragflow_client if user_message else None,
            allow_voice=config.tts_enabled,
        )

        # AI 决定用语音回复：只发语音
        if result.has_voice:
            history.append({
                "role": "assistant",
                "content": result.voice_text,
            })
            if len(history) > config.ai_context_limit:
                history = history[-config.ai_context_limit:]
            await set_user_history(user_id, history)
            try:
                audio = await synthesize(
                    result.voice_text,
                    result.voice_instruct or config.tts_instruct,
                )
            except Exception as e:
                logger.error(f"私聊语音生成失败，改为不发 用户:{user_id}: {e}")
                await private_msg.finish()
            logger.info(f"私聊语音回复 用户:{user_id} 内容:{result.voice_text[:20]}...")
            await private_msg.finish(
                MessageSegment.record(f"base64://{base64.b64encode(audio).decode()}")
            )

        reply = result.text

        # 空回复兜底：不发送、不写入历史（MiMo 偶发返回空内容）
        if not reply or not reply.strip():
            logger.warning(f"AI 返回空回复，静默跳过 用户:{user_id}")
            await private_msg.finish()

        # 添加助手回复到历史
        history.append({
            "role": "assistant",
            "content": reply,
        })

        # 限制历史记录长度
        if len(history) > config.ai_context_limit:
            history = history[-config.ai_context_limit:]
        
        # AI 回复后更新缓存
        await set_user_history(user_id, history)

        logger.info(f"私聊回复 用户:{user_id} 回复:{reply}")
        await private_msg.finish(reply)

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # AI 调用失败，回滚历史记录（移除本次用户消息，避免孤立消息污染上下文）
        await set_user_history(user_id, original_history)
        # 高风险拦截兜底回复
        if "high risk" in str(e).lower():
            await private_msg.finish("别发些乱七八糟的东西！")
        await private_msg.finish(f"AI 调用失败: {e}")

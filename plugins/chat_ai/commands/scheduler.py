from datetime import datetime
from pathlib import Path

import asyncio
import random
import time

from nonebot import get_plugin_config, require, logger, get_bot
from nonebot_plugin_apscheduler import scheduler

from ..config import Config
from .. import state
from ..state import (
    db,
    CHAT_LOG_DIR,
    group_last_activity,
    group_last_bubble,
    group_recent_messages,
)
from ..utils.helpers import get_time_period
from ..summarizer import generate_summary

# 各时间段预设冒泡语（带铃月弥口语风格，无标点）
BUBBLE_PRESET_LINES = {
    "清晨": ["早啊 群里居然有人醒了", "这么早就有人冒泡了", "早 今天吃啥"],
    "上午": ["好无聊 有人打游戏吗", "上午都在摸鱼吗", "群怎么这么安静"],
    "中午": ["中午吃啥啊", "都吃饭了吗", "吃饱了就开始困"],
    "下午": ["下午好闲", "没人聊天吗 那我也不说了", "好困 谁来逗逗我"],
    "晚上": ["晚上好呀 都在忙啥", "下班了 群里人呢", "夜猫子都出来了吗"],
    "深夜": ["大半夜的还不睡 修仙呢", "这个点就剩我一个了吗", "困了困了 谁还醒着"],
}


def _generate_preset_bubble() -> str:
    """从预设语库中随机选一句冒泡语"""
    lines = BUBBLE_PRESET_LINES.get(get_time_period(), BUBBLE_PRESET_LINES["下午"])
    return random.choice(lines)


async def _generate_bubble(group_id: int) -> str:
    """生成冒泡内容：优先用 AI 结合最近群聊生成，失败则回退预设语"""
    config = get_plugin_config(Config)
    if config.bubble_ai_enabled and state.ai_service:
        try:
            recent = group_recent_messages.get(group_id, [])
            if recent:
                ctx = "  ".join(text for _, text in recent[-5:] if text)
                user_prompt = f"群里最近聊过：{ctx}\n现在群里很冷清，你冒个泡说一句简短的话暖场，别@人，一句话就好。"
            else:
                user_prompt = "现在群里很冷清，你冒个泡说一句简短的话暖场，别@人，一句话就好。"
            reply = await asyncio.wait_for(
                state.ai_service.chat(
                    user_message=user_prompt,
                    system_prompt="你是铃月弥，一个整天泡在QQ群里的网瘾少女，说话口语化、嘴毒爱吐槽、看心情回消息。",
                    max_tokens=256,
                ),
                timeout=30,
            )
            reply = (reply or "").strip()
            if reply:
                # 只取第一句，并截断保证简短
                reply = reply.split("\n")[0].strip().strip("，。！？、；：\"\"''（）")
                if "<tool" not in reply:
                    if len(reply) > 40:
                        reply = reply[:40]
                    return reply
            logger.warning(f"AI 冒泡内容无效，使用预设: {reply!r}")
        except Exception as e:
            logger.warning(f"AI 冒泡生成失败，使用预设: {e}")
    return _generate_preset_bubble()


def _mark_as_uploaded(file_path: Path) -> None:
    """标记文件为已上传（重命名添加 _uploaded 后缀）"""
    uploaded_path = file_path.with_name(file_path.stem + "_uploaded" + file_path.suffix)
    try:
        file_path.rename(uploaded_path)
    except Exception as e:
        logger.error(f"标记文件已上传失败: {e}")


def _iter_unprocessed_logs(group_id: int, today_str: str) -> list[Path]:
    """收集群内所有「日期早于今天」且未上传的聊天记录文件"""
    paths: list[Path] = []
    for p in CHAT_LOG_DIR.glob(f"{group_id}_*.txt"):
        stem = p.stem
        if "_uploaded" in stem or "_summary" in stem:
            continue
        parts = stem.split("_")
        if len(parts) != 2:
            continue
        fdate = parts[1]
        # 跳过今天的在途文件，留到次日 0 点再处理
        if fdate >= today_str:
            continue
        paths.append(p)
    return sorted(paths)


@scheduler.scheduled_job("cron", hour=0, minute=0, id="daily_kb_upload")
async def daily_kb_upload():
    """每天凌晨0点上传昨日（及之前遗漏的）聊天记录与总结到知识库"""
    logger.info("开始执行每日知识库入库任务...")

    # 懒初始化，确保 RAGFlow 客户端可用（避免静默跳过）
    if not state.ai_service:
        state.init_ai_service()

    if not state.ragflow_client:
        logger.warning("RAGFlow 客户端未初始化，跳过入库任务")
        return

    config = get_plugin_config(Config)

    kb_groups = db.get_all_kb_groups()
    if not kb_groups:
        logger.info("没有配置知识库群，跳过入库任务")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    results = []

    for group_id, kb_id in kb_groups.items():
        log_paths = _iter_unprocessed_logs(group_id, today_str)
        if not log_paths:
            results.append(f"群 {group_id}: 无待上传的历史聊天记录")
            continue

        for log_path in log_paths:
            date_str = log_path.stem.split("_")[-1]

            if log_path.stat().st_size == 0:
                _mark_as_uploaded(log_path)
                results.append(f"群 {group_id}: {date_str} 聊天记录为空，标记跳过")
                continue

            # 先根据原始聊天记录生成总结（需在原始文件重命名前读取）
            summary_path = None
            if config.kb_summary_enabled:
                try:
                    summary_path = await generate_summary(group_id, date_str, log_path)
                except Exception as e:
                    logger.error(f"群 {group_id} {date_str} 生成聊天总结失败: {e}")

            success = await state.ragflow_client.upload_and_parse(kb_id, log_path)
            if success:
                _mark_as_uploaded(log_path)
                results.append(f"群 {group_id}: {date_str} 原始记录上传成功 -> 知识库 {kb_id}")
            else:
                results.append(f"群 {group_id}: {date_str} 原始记录上传失败")

            if summary_path:
                summary_ok = await state.ragflow_client.upload_and_parse(kb_id, summary_path)
                if summary_ok:
                    _mark_as_uploaded(summary_path)
                    results.append(f"群 {group_id}: {date_str} 总结上传成功 -> 知识库 {kb_id}")
                else:
                    results.append(f"群 {group_id}: {date_str} 总结上传失败")

    for r in results:
        logger.info(f"入库结果: {r}")

    logger.info(f"每日知识库入库任务完成，共处理 {len(kb_groups)} 个群")


@scheduler.scheduled_job("interval", minutes=15, id="group_bubble_check")
async def group_bubble_check():
    """主动冒泡：每隔一段时间检查群是否冷清，冷清了就主动说句话"""
    config = get_plugin_config(Config)
    if not config.bubble_enabled:
        return

    # 禁言期间不冒泡
    if time.time() < state.bot_mute_until:
        return

    # 确保 AI 服务可用（AI 冒泡需要）
    if not state.ai_service:
        state.init_ai_service()

    try:
        bot = get_bot()
    except Exception as e:
        logger.warning(f"获取 bot 失败，跳过冒泡: {e}")
        return

    now = time.time()
    idle_seconds = config.bubble_idle_minutes * 60
    cooldown_seconds = config.bubble_cooldown_minutes * 60

    groups = db.get_all_groups()
    for group_id in groups:
        last_activity = group_last_activity.get(group_id, 0)
        # 从未记录过活跃的群不冒泡
        if not last_activity:
            continue
        # 群里还不算冷清
        if now - last_activity < idle_seconds:
            continue
        # 冒泡冷却中
        if now - group_last_bubble.get(group_id, 0) < cooldown_seconds:
            continue
        # 概率命中
        if random.random() > config.bubble_chance:
            continue

        content = await _generate_bubble(group_id)
        try:
            await bot.send_group_msg(group_id=group_id, message=content)
            group_last_bubble[group_id] = time.time()
            logger.info(f"主动冒泡 群:{group_id} 内容:{content}")
        except Exception as e:
            logger.error(f"冒泡发送失败 群:{group_id}: {e}")

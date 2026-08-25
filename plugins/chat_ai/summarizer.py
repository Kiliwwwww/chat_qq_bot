from pathlib import Path

from nonebot import get_plugin_config, logger

from .config import Config
from . import state


SUMMARY_PROMPT = """你是群聊记录的归纳总结助手。我会给你一段群聊记录，请你对这段记录进行归纳总结，输出结构化 Markdown。

要求：
1. 严格忠于原文，不得编造不存在的消息、成员或事实
2. 全程使用中文
3. 用以下 Markdown 结构输出，没有对应内容的板块直接省略：
### 讨论话题
列举讨论的主要话题，每个话题一句话概括
### 讨论要点
按话题列出核心内容、大家的观点和分歧
### 决策与约定
记录群里明确的决定、约好的安排、承诺等
### 值得记住的片段
有趣的发言、金句、爆点
4. 保持客观中立，不要加个人评价
"""


COMBINE_PROMPT = """以下是同一时间段群聊记录的多份分块总结。请将它们合并为一份完整、无重复的总结，保留所有重要信息，去除重复内容，输出结构化 Markdown。

要求：
1. 严格忠于原文，不得编造不存在的消息、成员或事实
2. 全程使用中文
3. 使用以下结构：
### 讨论话题
### 讨论要点
### 决策与约定
### 值得记住的片段
4. 保持客观中立，不要加个人评价
"""


def _split_into_chunks(content: str, max_chars: int) -> list[str]:
    """按行将内容切分为不超过 max_chars 字符的分块"""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in content.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


async def _summarize_text(ai, text: str, system_prompt: str, model: str | None, max_tokens: int) -> str:
    reply = await ai.chat(
        user_message=text,
        system_prompt=system_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return (reply or "").strip()


async def generate_summary(group_id: int, date_str: str, log_path: Path) -> Path | None:
    """
    对聊天记录文件生成归纳总结并写入 *_summary.txt 文件

    Args:
        group_id: 群号
        date_str: 日期字符串 YYYY-MM-DD
        log_path: 聊天记录文件路径

    Returns:
        总结文件路径，失败返回 None
    """
    config = get_plugin_config(Config)

    if not state.ai_service:
        state.init_ai_service()
    if not state.ai_service:
        logger.error("AI 服务未初始化，无法生成聊天记录总结")
        return None

    try:
        content = log_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"读取聊天记录失败: {log_path}: {e}")
        return None

    if not content.strip():
        logger.warning(f"聊天记录为空，跳过总结: {log_path}")
        return None

    model = config.kb_summary_model or None
    chunks = _split_into_chunks(content, config.kb_summary_max_chars)
    logger.info(f"开始生成群 {group_id} {date_str} 聊天总结，共 {len(chunks)} 块")

    summaries: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"正在总结第 {i}/{len(chunks)} 块...")
        try:
            partial = await _summarize_text(
                state.ai_service,
                chunk,
                SUMMARY_PROMPT,
                model,
                config.ai_max_tokens,
            )
            if partial:
                summaries.append(partial)
        except Exception as e:
            logger.error(f"总结第 {i} 块失败: {e}")

    if not summaries:
        logger.error("所有分块总结均失败，放弃生成总结")
        return None

    if len(summaries) > 1:
        logger.info("正在合并分块总结...")
        combined = ""
        try:
            combined = await _summarize_text(
                state.ai_service,
                "\n\n---\n\n".join(f"## 第{i}部分\n{s}" for i, s in enumerate(summaries, 1)),
                COMBINE_PROMPT,
                model,
                config.ai_max_tokens * 2,
            )
        except Exception as e:
            logger.error(f"合并总结失败: {e}")
        final_summary = combined or "\n\n".join(summaries)
    else:
        final_summary = summaries[0]

    summary_path = log_path.with_name(f"{log_path.stem}_summary{log_path.suffix}")
    try:
        header = f"# 群 {group_id} 聊天记录总结（{date_str}）\n\n"
        summary_path.write_text(header + final_summary, encoding="utf-8")
        logger.info(f"聊天记录总结已生成: {summary_path}")
        return summary_path
    except Exception as e:
        logger.error(f"写入总结文件失败: {e}")
        return None

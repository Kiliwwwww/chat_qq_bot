from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent

from ..state import db

stats_cmd = on_command("stats", aliases={"统计"}, priority=5, block=True)


@stats_cmd.handle()
async def handle_stats(event: MessageEvent):
    """显示统计数据"""
    all_stats = db.get_all_stats()

    kb_retrieve = all_stats.get("kb_retrieve_count", 0)
    kb_upload = all_stats.get("kb_upload_count", 0)
    kb_parse = all_stats.get("kb_parse_count", 0)
    ai_request = all_stats.get("ai_request_count", 0)

    stats_text = f"""统计数据：
检索知识库：{kb_retrieve} 次
上传知识库：{kb_upload} 次
解析知识库：{kb_parse} 次
AI接口请求：{ai_request} 次"""

    await stats_cmd.finish(stats_text)

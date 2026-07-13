from nonebot import on_command, get_plugin_config, on_message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message
from nonebot.params import CommandArg
from nonebot import logger
import redis
import json
from datetime import datetime
from typing import Optional

from .config import Config

# 获取配置
config = get_plugin_config(Config)

# Redis 连接（带错误处理）
redis_client = None
try:
    redis_client = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password if config.redis_password else None,
        decode_responses=config.redis_decode_responses,
    )
    # 测试连接
    redis_client.ping()
    logger.info("Redis 连接成功")
except Exception as e:
    logger.error(f"Redis 连接失败: {e}，排行榜功能将不可用")
    redis_client = None

# 排行榜命令
ranking_cmd = on_command("排行榜", aliases={"ranking"}, priority=5, block=True)


def get_today_str() -> str:
    """获取今天的日期字符串"""
    return datetime.now().strftime("%Y%m%d")


def get_message_count_key(group_id: int) -> str:
    """获取群消息计数的Redis key（包含日期）"""
    today = get_today_str()
    return f"ranking:group:{group_id}:{today}"


def increment_message_count(group_id: int, user_id: int) -> int:
    """增加用户消息计数，返回当前计数"""
    key = get_message_count_key(group_id)
    field = str(user_id)
    # 增加计数
    count = redis_client.hincrby(key, field, 1)
    # 设置key过期时间为2天（172800秒），自动清理旧数据
    redis_client.expire(key, 172800)
    return count


def get_top_users(group_id: int, top_n: int = 5) -> list[tuple[int, int]]:
    """获取群内发言排行榜前N名"""
    key = get_message_count_key(group_id)
    # 获取所有用户的消息计数
    all_users = redis_client.hgetall(key)
    if not all_users:
        return []
    
    # 转换为 (user_id, count) 元组列表并排序
    user_counts = [(int(uid), int(count)) for uid, count in all_users.items()]
    user_counts.sort(key=lambda x: x[1], reverse=True)
    
    return user_counts[:top_n]


async def get_user_nickname(bot, group_id: int, user_id: int) -> str:
    """获取用户在群里的昵称，优先群昵称，其次QQ昵称，最后用QQ号"""
    try:
        info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        return info.get("card") or info.get("nickname") or str(user_id)
    except Exception:
        return str(user_id)


async def format_ranking_message(top_users: list[tuple[int, int]], group_id: int, bot) -> str:
    """格式化排行榜消息"""
    if not top_users:
        return "今日暂无发言数据"
    
    today = datetime.now().strftime("%Y-%m-%d")
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    lines = [f"📊 群 {group_id} 今日发言排行榜（{today}）：", ""]
    
    for i, (user_id, count) in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        nickname = await get_user_nickname(bot, group_id, user_id)
        lines.append(f"{medal} {nickname} - {count} 条消息")
    
    return "\n".join(lines)


@ranking_cmd.handle()
async def handle_ranking(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """处理排行榜命令"""
    # 检查Redis是否可用
    if redis_client is None:
        await ranking_cmd.finish("排行榜功能暂不可用（Redis未连接）")
    
    group_id = event.group_id
    top_users = get_top_users(group_id, 5)
    message = await format_ranking_message(top_users, group_id, bot)
    
    await ranking_cmd.finish(message)


# 群消息计数处理器
group_msg_counter = on_message(priority=1, block=False)


@group_msg_counter.handle()
async def handle_group_message(event: GroupMessageEvent):
    """统计群消息"""
    # 检查Redis是否可用
    if redis_client is None:
        return
    
    group_id = event.group_id
    user_id = event.user_id
    
    try:
        # 增加消息计数
        count = increment_message_count(group_id, user_id)
        logger.debug(f"群 {group_id} 用户 {user_id} 消息计数: {count}")
    except Exception as e:
        logger.error(f"消息计数失败: {e}")
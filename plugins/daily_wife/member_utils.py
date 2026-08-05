import random
from typing import Optional

import httpx
from nonebot.adapters.onebot.v11 import Bot
from nonebot import logger


def get_avatar_url(user_id: int) -> str:
    """获取QQ头像URL"""
    return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"


async def download_avatar(user_id: int) -> Optional[bytes]:
    """下载用户头像，返回图片字节数据"""
    url = get_avatar_url(user_id)
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, timeout=15.0)
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"下载头像失败: user_id={user_id}, status={response.status_code}, url={url}")
                return None
    except Exception as e:
        logger.error(f"下载头像异常: user_id={user_id}, error={type(e).__name__}: {e}, url={url}")
        return None


async def get_user_nickname(bot: Bot, group_id: int, user_id: int) -> str:
    """获取用户在群里的昵称，优先群昵称，其次QQ昵称，最后用QQ号"""
    try:
        info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        return info.get("card") or info.get("nickname") or str(user_id)
    except Exception:
        return str(user_id)


async def get_random_member(bot: Bot, group_id: int, exclude_user_id: Optional[int] = None) -> Optional[dict]:
    """随机获取一个群成员
    
    Args:
        bot: Bot 实例
        group_id: 群号
        exclude_user_id: 要排除的用户ID（通常是发送者自己）
    
    Returns:
        群成员信息字典，如果没有可用成员则返回 None
    """
    try:
        members = await bot.get_group_member_list(group_id=group_id)
        if not members:
            return None
        
        # 排除指定用户
        if exclude_user_id is not None:
            members = [m for m in members if m["user_id"] != exclude_user_id]
        
        if not members:
            return None
        
        return random.choice(members)
    except Exception as e:
        logger.error(f"获取群成员列表失败: group_id={group_id}, error={e}")
        return None

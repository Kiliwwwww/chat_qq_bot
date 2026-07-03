import re
import sqlite3
from pathlib import Path
import httpx
import nonebot
from nonebot import on_command, require
from nonebot.adapters.onebot.v11 import MessageEvent, Message, MessageSegment, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot import logger
from nonebot.exception import FinishedException

from .config import Config

# 依赖 localstore 插件
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

# 使用chat_ai插件的数据库（避免导入chat_ai插件导致重复注册处理器）
# 构建chat_ai数据库的路径
project_root = Path(__file__).parent.parent.parent
db_path = project_root / "data" / "chat_ai" / "chat_ai.db"


def user_exists(user_id: int) -> bool:
    """检查用户是否在白名单中"""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,)
        )
        result = cursor.fetchone() is not None
        conn.close()
        return result
    except Exception as e:
        logger.error(f"检查用户失败: {e}")
        return False


async def download_image(url: str) -> bytes | None:
    """下载图片，返回图片数据"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                'Referer': 'https://m.weibo.cn/',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'
            }
            logger.info(f"开始下载图片: {url}")
            resp = await client.get(url, headers=headers, follow_redirects=True, timeout=30)
            logger.info(f"下载响应状态: {resp.status_code}, 内容大小: {len(resp.content)}")
            if resp.status_code == 200 and len(resp.content) > 0:
                return resp.content
            else:
                logger.error(f"下载图片失败: status={resp.status_code}")
                return None
    except Exception as e:
        logger.error(f"下载图片异常: {e}")
        return None


async def get_weibo_image(uid: int) -> bytes | None:
    """获取用户最新有图片的微博图片，返回图片数据"""
    try:
        from mcp_server_weibo.weibo import WeiboCrawler
        crawler = WeiboCrawler()
        
        # 获取用户动态
        feeds = await crawler.get_feeds(uid, limit=10)
        if not feeds:
            return None
        
        # 按 created_at 排序，取最新的
        from datetime import datetime
        def parse_time(feed):
            try:
                return datetime.strptime(feed.created_at, "%a %b %d %H:%M:%S %z %Y")
            except:
                return datetime.min
        feeds.sort(key=parse_time, reverse=True)
        
        # 找到最新一条有图片的帖子
        for feed in feeds:
            if feed.pics and len(feed.pics) > 0:
                # 获取图片URL
                pic = feed.pics[0]
                if isinstance(pic, dict):
                    img_url = pic.get('large') or pic.get('thumbnail')
                else:
                    img_url = getattr(pic, 'large', None) or getattr(pic, 'thumbnail', None)
                if img_url:
                    return await download_image(img_url)
        
        return None
    except Exception as e:
        logger.error(f"获取微博图片失败: {e}")
        return None


# 注册命令
weibo_cmd = on_command("weibo", priority=5, block=True)
sendweibo_cmd = on_command("sendweibo", priority=5, block=True)


@weibo_cmd.handle()
async def handle_weibo(event: MessageEvent, args: Message = CommandArg()):
    """处理/weibo命令"""
    # 只处理私聊消息
    if not isinstance(event, PrivateMessageEvent):
        await weibo_cmd.finish("此命令仅支持私聊使用")

    # 检查用户是否在白名单中
    if not user_exists(event.user_id):
        await weibo_cmd.finish("权限不足，您不在白名单中")

    # 提取UID参数
    uid_str = args.extract_plain_text().strip()
    if not uid_str:
        await weibo_cmd.finish("请提供微博用户UID，例如：/weibo 1234567")

    try:
        uid = int(uid_str)
    except ValueError:
        await weibo_cmd.finish("UID必须是数字")

    try:
        # 导入WeiboCrawler
        from mcp_server_weibo.weibo import WeiboCrawler

        # 创建爬虫实例
        crawler = WeiboCrawler()

        # 获取用户动态（获取多条，找有图片的）
        feeds = await crawler.get_feeds(uid, limit=10)

        if not feeds:
            await weibo_cmd.finish(f"未找到用户 {uid} 的动态")

        # 打印所有帖子的JSON数据
        for i, feed in enumerate(feeds):
            logger.info(f"帖子 {i+1}: {feed.model_dump_json(indent=2)}")

        # 按 created_at 排序，取最新的
        from datetime import datetime
        def parse_time(feed):
            try:
                return datetime.strptime(feed.created_at, "%a %b %d %H:%M:%S %z %Y")
            except:
                return datetime.min
        feeds.sort(key=parse_time, reverse=True)

        # 找到最新一条有图片的帖子
        target_feed = None
        for feed in feeds:
            logger.info(f"帖子 {feed.id} pics: {feed.pics}")
            if feed.pics and len(feed.pics) > 0:
                target_feed = feed
                logger.info(f"找到有图片的帖子: {feed.id}")
                break

        # 如果没有有图片的帖子，使用最新的帖子
        if not target_feed:
            target_feed = feeds[0]
            logger.info(f"没有有图片的帖子，使用最新的: {target_feed.id}")

        # 格式化输出
        text = target_feed.text or "无内容"
        # 清理HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('<br />', '\n').replace('<br/>', '\n')

        # 获取用户信息
        user = target_feed.user
        user_name = user.screen_name if user else "未知用户"

        # 构建回复消息
        reply = f"【微博动态】\n"
        reply += f"用户：{user_name}\n"
        reply += f"时间：{target_feed.created_at}\n"
        reply += f"来源：{target_feed.source}\n"
        reply += f"内容：{text[:500]}{'...' if len(text) > 500 else ''}\n"
        reply += f"点赞：{target_feed.attitudes_count} | 评论：{target_feed.comments_count} | 转发：{target_feed.reposts_count}\n"

        # 添加链接
        reply += f"链接：https://m.weibo.cn/detail/{target_feed.id}"

        # 先发送文字信息
        await weibo_cmd.send(reply)

        # 如果有图片，发送图片
        if target_feed.pics:
            logger.info(f"帖子有 {len(target_feed.pics)} 张图片")
            msg = Message()
            for i, pic in enumerate(target_feed.pics):
                # pics是字典列表，使用字典方式访问
                if isinstance(pic, dict):
                    img_url = pic.get('large') or pic.get('thumbnail')
                else:
                    img_url = getattr(pic, 'large', None) or getattr(pic, 'thumbnail', None)
                logger.info(f"图片 {i+1} URL: {img_url}")
                if img_url:
                    # 下载图片
                    img_data = await download_image(img_url)
                    if img_data:
                        msg += MessageSegment.image(img_data)
                        logger.info(f"图片 {i+1} 下载成功")
                    else:
                        logger.error(f"图片 {i+1} 下载失败")
            if msg:
                await weibo_cmd.finish(msg)
        await weibo_cmd.finish()

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"获取微博动态失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await weibo_cmd.finish(f"获取微博动态失败: {str(e)}")


@sendweibo_cmd.handle()
async def handle_sendweibo(event: MessageEvent, args: Message = CommandArg()):
    """处理/sendweibo命令，发送微博图片到指定群"""
    # 只处理私聊消息
    if not isinstance(event, PrivateMessageEvent):
        await sendweibo_cmd.finish("此命令仅支持私聊使用")

    # 检查用户是否在白名单中
    if not user_exists(event.user_id):
        await sendweibo_cmd.finish("权限不足，您不在白名单中")

    # 提取参数：uid 群号
    arg_str = args.extract_plain_text().strip()
    if not arg_str:
        await sendweibo_cmd.finish("请提供参数，例如：/sendweibo 1234567 987654321")

    parts = arg_str.split()
    if len(parts) != 2:
        await sendweibo_cmd.finish("参数格式错误，请使用：/sendweibo uid 群号")

    try:
        uid = int(parts[0])
        group_id = int(parts[1])
    except ValueError:
        await sendweibo_cmd.finish("UID和群号必须是数字")

    try:
        # 获取微博图片
        img_data = await get_weibo_image(uid)
        if not img_data:
            await sendweibo_cmd.finish(f"未找到用户 {uid} 的带图片动态")

        # 发送到指定群
        msg = Message()
        msg += MessageSegment.text("今日自拍\n")
        msg += MessageSegment.image(img_data)

        bot = nonebot.get_bot()
        await bot.send_group_msg(group_id=group_id, message=msg)

        await sendweibo_cmd.finish(f"已发送到群 {group_id}")

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"发送微博到群失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await sendweibo_cmd.finish(f"发送失败: {str(e)}")
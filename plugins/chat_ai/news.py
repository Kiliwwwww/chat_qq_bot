"""今日新闻：微博热搜 + 知乎热榜。

数据源：
- 微博热搜榜：weibo.com 侧边栏热搜接口（自动跳过广告位与置顶要闻），
  接口异常时回退到 mcp-server-weibo 提供的爬虫。
- 知乎热榜：知乎 App 的 topstory 热榜接口，无需登录。

管理员私聊发送「今日新闻」或用定时任务（默认每天早上 09:00，可配置）触发，
内容会推送到 groupsettings 群白名单里的所有群。
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx
from nonebot import get_bot, logger

from .state import db

# 微博热搜榜（PC 侧边栏接口，无需 Cookie）
WEIBO_HOT_URL = "https://weibo.com/ajax/side/hotSearch"
# 知乎热榜（App 接口，无需登录）
ZHIHU_HOT_URL = "https://api.zhihu.com/topstory/hot-list"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_weibo_hot(limit: int = 5) -> list[str]:
    """抓取微博热搜榜前 limit 条（自动跳过广告位与置顶要闻）。"""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                WEIBO_HOT_URL,
                headers={"User-Agent": _UA, "Referer": "https://weibo.com/"},
            )
            resp.raise_for_status()
            realtime = (resp.json().get("data") or {}).get("realtime") or []

        words = [
            str(item.get("word", "")).strip()
            for item in realtime
            if not item.get("is_ad") and str(item.get("word", "")).strip()
        ]
        if words:
            return words[:limit]
        logger.warning("微博热搜接口没有返回数据，改用 mcp-server-weibo 爬虫")
    except Exception as e:
        logger.warning(f"微博热搜接口抓取失败，改用 mcp-server-weibo 爬虫: {e}")

    return await _fetch_weibo_hot_by_crawler(limit)


async def _fetch_weibo_hot_by_crawler(limit: int) -> list[str]:
    """备用方案：mcp-server-weibo 爬虫（置顶与广告条目的热度为 0，据此过滤）。"""
    try:
        from mcp_server_weibo.weibo import WeiboCrawler

        items = await WeiboCrawler().get_trendings(limit=limit + 5)
        words = [
            item.description.strip()
            for item in items
            if item.trending > 0 and item.description
        ]
        return words[:limit]
    except Exception as e:
        logger.error(f"微博热搜抓取失败: {e}")
        return []


async def fetch_zhihu_hot(limit: int = 5) -> list[str]:
    """抓取知乎热榜前 limit 条。"""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                ZHIHU_HOT_URL,
                params={"limit": max(limit, 10), "reverse_order": 0},
                headers={"User-Agent": _UA},
            )
            resp.raise_for_status()
            data = resp.json().get("data") or []
    except Exception as e:
        logger.error(f"知乎热榜抓取失败: {e}")
        return []

    titles: list[str] = []
    for item in data:
        title = str((item.get("target") or {}).get("title", "")).strip()
        if title:
            titles.append(title)
        if len(titles) >= limit:
            break
    return titles


async def fetch_news(weibo_count: int = 5, zhihu_count: int = 5) -> tuple[list[str], list[str]]:
    """并发抓取两个榜单，返回 (微博热搜, 知乎热榜)。"""
    weibo, zhihu = await asyncio.gather(
        fetch_weibo_hot(weibo_count),
        fetch_zhihu_hot(zhihu_count),
    )
    return weibo, zhihu


def _format_ranking(name: str, titles: list[str]) -> str:
    if not titles:
        return f"{name}\n（暂时获取失败）"
    body = "\n".join(f"{index}. {title}" for index, title in enumerate(titles, 1))
    return f"{name}\n{body}"


def format_news_text(
    weibo: list[str],
    zhihu: list[str],
    now: datetime | None = None,
) -> str:
    """按约定格式拼装今日新闻文本。"""
    moment = now or datetime.now()
    header = f"北京时间：{moment.strftime('%Y-%m-%d %H:%M')}"
    return "\n".join(
        [
            header,
            "",
            _format_ranking("微博热搜", weibo),
            _format_ranking("知乎热榜", zhihu),
        ]
    )


async def send_news_to_all_groups(text: str) -> tuple[int, int]:
    """把新闻文本发送到 groupsettings 群白名单里的所有群，返回 (成功数, 失败数)。"""
    groups = sorted(db.get_all_groups())
    if not groups:
        return 0, 0

    try:
        bot = get_bot()
    except Exception as e:
        logger.error(f"今日新闻：获取 bot 失败，本次发送中止: {e}")
        return 0, len(groups)

    ok = 0
    fail = 0
    for index, group_id in enumerate(groups):
        if index:
            # 群与群之间稍微间隔，避免发得太快被风控
            await asyncio.sleep(1)
        try:
            await bot.send_group_msg(group_id=group_id, message=text)
            ok += 1
        except Exception as e:
            fail += 1
            logger.error(f"今日新闻发送失败 群:{group_id}: {e}")
    return ok, fail

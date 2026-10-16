from nonebot import get_plugin_config, logger, on_command
from nonebot.adapters.onebot.v11 import MessageEvent

from ..config import Config
from ..news import fetch_news, format_news_text, send_news_to_all_groups

today_news_cmd = on_command("今日新闻", priority=5, block=True)


@today_news_cmd.handle()
async def handle_today_news(event: MessageEvent):
    """管理员发送「今日新闻」：抓取微博热搜 + 知乎热榜并推送到所有白名单群"""
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await today_news_cmd.finish("只有管理员可以使用此命令")

    await today_news_cmd.send("正在抓取今日新闻，稍等一下…")

    weibo, zhihu = await fetch_news(
        config.daily_news_weibo_count,
        config.daily_news_zhihu_count,
    )
    if not weibo and not zhihu:
        await today_news_cmd.finish("微博热搜和知乎热榜都没抓到数据，稍后再试试吧")

    text = format_news_text(weibo, zhihu)
    ok, fail = await send_news_to_all_groups(text)

    if ok == 0 and fail == 0:
        await today_news_cmd.finish("群列表是空的，先用 /groupsettings <群号> 添加群")

    tips = []
    if not weibo:
        tips.append("微博热搜抓取失败")
    if not zhihu:
        tips.append("知乎热榜抓取失败")

    summary = f"已推送到 {ok} 个群"
    if fail:
        summary += f"，{fail} 个群发送失败"
    if tips:
        summary += "\n（" + "，".join(tips) + "）"

    logger.info(f"今日新闻手动推送完成：成功 {ok} 个群，失败 {fail} 个群")
    await today_news_cmd.finish(summary)

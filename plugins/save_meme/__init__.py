"""存表情：管理员私聊把图片按目录存到本地。

用法：
    /存表情 /分类/子分类   开启收图，之后发来的图片都会存进该目录
    /存表情结束            结束收图
    /存表情                查看当前收图状态

只在私聊、只对管理员生效；收图期间发来的图片不会再交给 AI 处理。
"""

from __future__ import annotations

from nonebot import get_plugin_config, logger, on_command, on_message
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import Message, MessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg

from .config import Config
from .saver import (
    DEFAULT_FOLDER,
    SaveSession,
    end_session,
    get_session,
    is_in_library,
    library_count,
    parse_directory,
    refresh_library_if_needed,
    save_image,
    start_session,
)

config = get_plugin_config(Config)

save_meme_cmd = on_command("存表情", priority=5, block=True)
save_meme_end_cmd = on_command("存表情结束", priority=5, block=True)


async def _collecting_images(event: MessageEvent) -> bool:
    """收图拦截的匹配条件：管理员私聊 + 正在收图 + 这条消息带图片

    条件必须写成 rule，不能写在 handler 里 `skip()`：NoneBot 2.5 里
    block=True 的匹配器即使 skip() 了也会阻断更低优先级的匹配器，写在
    handler 里会把私聊命令、群消息和 AI 对话全部吃掉。放进 rule 后，
    不匹配时匹配器压根不会运行，事件照常往后传。
    """
    if not isinstance(event, PrivateMessageEvent):
        return False
    if event.user_id != config.admin_qq:
        return False
    if get_session(event.user_id) is None:
        return False
    return any(seg.type == "image" for seg in event.get_message())


# 收图期间把管理员发来的图片截下来，优先级放得比所有命令和 AI 对话都高
save_meme_image = on_message(rule=Rule(_collecting_images), priority=3, block=True)

# 一波连发的图片只在开头回一句，避免每张图都刷一条消息
_REPLY_GAP_SECONDS = 5.0


async def _check_admin(matcher, event: MessageEvent) -> None:
    """私聊 + 管理员校验，不通过时直接结束这个匹配器"""
    if not isinstance(event, PrivateMessageEvent):
        await matcher.finish("这个命令只能在私聊里用哦")
    if event.user_id != config.admin_qq:
        await matcher.finish("只有管理员可以使用此命令")


def _status_text(session: SaveSession) -> str:
    text = f"正在收图 → {session.directory}\n已存 {session.saved} 张"
    if session.failed:
        text += f"，失败 {session.failed} 张"
    return text + "\n发 /存表情结束 结束；想换目录发 /存表情 /分组/子分组"


def _end_text(user_id: int) -> str:
    session = end_session(user_id)
    if session is None:
        return "当前没有在收图，发 /存表情 /目录 可以开始"
    text = f"收图结束，共保存 {session.saved} 张 → {session.directory}"
    if session.failed:
        text += f"\n（有 {session.failed} 张没存成功，详见日志）"
    if session.oversized:
        text += (
            f"\n（其中 {session.oversized} 张超过奶龙库体积上限，存下来了但不会被抽到，"
            f"想用上的话把 meme_max_bytes 调大）"
        )
    return text


@save_meme_cmd.handle()
async def _handle_save_meme(event: MessageEvent, args: Message = CommandArg()):
    """开启收图：/存表情 /分类/子分类"""
    await _check_admin(save_meme_cmd, event)

    arg = args.extract_plain_text().strip()
    if arg in {"结束", "end", "stop"}:
        await save_meme_cmd.finish(_end_text(event.user_id))

    if not arg:
        session = get_session(event.user_id)
        if session:
            await save_meme_cmd.finish(_status_text(session))

    directory, error = parse_directory(arg)
    if directory is None:
        await save_meme_cmd.finish(error)

    old = start_session(event.user_id, directory)
    tip = ""
    if old:
        tip = f"\n（原来在收 {old.directory}，已切过来，那边存了 {old.saved} 张）"
    if not arg:
        tip += f"\n（没写目录，默认存到「{DEFAULT_FOLDER}」目录）"

    in_library = is_in_library(directory)
    if in_library:
        tip += "\n这些图会直接进奶龙表情库，/今日奶龙 和开启奶龙后的 AI 跟图都能抽到"
    logger.info(f"管理员 {event.user_id} 开启存表情 → {directory}（奶龙库: {in_library}）")
    await save_meme_cmd.finish(
        f"开始收图 → {directory}\n现在开始发图片，我都会存进去；发 /存表情结束 就停{tip}"
    )


@save_meme_end_cmd.handle()
async def _handle_save_meme_end(event: MessageEvent):
    """结束收图：/存表情结束"""
    await _check_admin(save_meme_end_cmd, event)
    logger.info(f"管理员 {event.user_id} 结束存表情")
    await save_meme_end_cmd.finish(_end_text(event.user_id))


@save_meme_image.handle()
async def _handle_save_meme_image(event: MessageEvent):
    """保存管理员在收图期间发来的图片（只有命中 rule 才会走到这里）"""
    session = get_session(event.user_id)
    images = [seg for seg in event.get_message() if seg.type == "image"]
    if session is None or not images:  # rule 已保证不会走到这里，仅兜底
        await save_meme_image.finish()

    gap = session.seconds_since_last_save
    before = session.saved
    for segment in images:
        await save_image(segment, session)
    added = session.saved - before

    if not added:
        logger.warning(f"[存表情] 用户 {event.user_id} 发来的 {len(images)} 张图片都没存成功")
        await save_meme_image.finish("这几张没存成功，看下日志吧")

    # 存进奶龙库的话刷新一下缓存，刚存的图立刻就能被 /今日奶龙 抽到
    await refresh_library_if_needed(session.directory)

    if gap > _REPLY_GAP_SECONDS:
        text = f"已存 {added} 张（累计 {session.saved} 张）"
        if is_in_library(session.directory):
            text += f"\n奶龙库现有 {library_count()} 张，/今日奶龙 现在就能抽到"
        await save_meme_image.finish(text)
    await save_meme_image.finish()

import time

from nonebot import get_plugin_config, logger, on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from .config import Config
from .netease import extract_song_id, get_song, search_songs

config = get_plugin_config(Config)

# 点歌候选缓存: (session_id, user_id) -> (timestamp, [Song])
_candidates: dict[tuple[str, int], tuple[float, list]] = {}

dian_ge_cmd = on_command("点歌", aliases={"点首歌"}, priority=5, block=True)
xuan_ge_cmd = on_command("选歌", priority=5, block=True)


def _cache_key(event: MessageEvent) -> tuple[str, int]:
    return (event.get_session_id(), event.user_id)


def _get_candidates(event: MessageEvent) -> list | None:
    key = _cache_key(event)
    cached = _candidates.get(key)
    if not cached:
        return None
    ts, songs = cached
    if time.time() - ts > config.music_cache_ttl:
        _candidates.pop(key, None)
        return None
    return songs


def _set_candidates(event: MessageEvent, songs: list) -> None:
    _candidates[_cache_key(event)] = (time.time(), songs)


def _build_card(song) -> Message:
    return MessageSegment.music("163", song.id)


def _build_list_text(songs: list, selected: int = 0) -> str:
    lines = []
    for i, song in enumerate(songs):
        mark = "▶ " if i == selected else f"{i + 1}. "
        lines.append(f"{mark}{song.name} - {song.artist_text}")
    return "\n".join(lines)


@dian_ge_cmd.handle()
async def handle_dian_ge(event: MessageEvent, args: Message = CommandArg()):
    keyword = args.extract_plain_text().strip()
    if not keyword:
        await dian_ge_cmd.finish("用法：点歌 <歌名/歌手> 或 点歌 <网易云歌曲链接>")

    # 直接给链接的情况：提取歌曲 ID 发卡片
    song_id = await extract_song_id(keyword)
    if song_id:
        try:
            song = await get_song(song_id)
        except Exception as e:
            logger.error(f"获取歌曲详情失败: {e}")
            song = None
        if song:
            _set_candidates(event, [song])
            await dian_ge_cmd.finish(
                Message(_build_card(song)) + f"\n{song.name} - {song.artist_text}"
            )
        await dian_ge_cmd.finish(MessageSegment.music("163", song_id))

    # 关键词搜索
    try:
        songs = await search_songs(keyword, config.music_search_limit)
    except Exception as e:
        logger.error(f"网易云搜索失败: {e}")
        await dian_ge_cmd.finish("搜索失败了，稍后再试试~")

    if not songs:
        await dian_ge_cmd.finish(f"没搜到「{keyword}」相关的歌曲~")

    _set_candidates(event, songs)
    first = songs[0]
    msg = Message(_build_card(first))
    if len(songs) > 1:
        msg += f"\n{ _build_list_text(songs) }\n发送「选歌 <序号>」切换"
    await dian_ge_cmd.finish(msg)


@xuan_ge_cmd.handle()
async def handle_xuan_ge(event: MessageEvent, args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    songs = _get_candidates(event)
    if not songs:
        await xuan_ge_cmd.finish("没有可切换的歌曲，请先「点歌」")

    if not arg.isdigit() or not 1 <= int(arg) <= len(songs):
        await xuan_ge_cmd.finish(f"请输入 1-{len(songs)} 的序号")

    song = songs[int(arg) - 1]
    await xuan_ge_cmd.finish(
        Message(_build_card(song)) + f"\n{song.name} - {song.artist_text}"
    )

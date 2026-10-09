from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from .netease import extract_song_id, get_song, search_songs

dian_ge_cmd = on_command("点歌", aliases={"点首歌"}, priority=5, block=True)


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
            await dian_ge_cmd.finish(
                Message(MessageSegment.music("163", song.id))
                + f"\n{song.name} - {song.artist_text}"
            )
        await dian_ge_cmd.finish(MessageSegment.music("163", song_id))

    # 关键词搜索，直接取第一条
    try:
        songs = await search_songs(keyword, limit=5)
    except Exception as e:
        logger.error(f"网易云搜索失败: {e}")
        await dian_ge_cmd.finish("搜索失败了，稍后再试试~")

    if not songs:
        await dian_ge_cmd.finish(f"没搜到「{keyword}」相关的歌曲~")

    song = songs[0]
    await dian_ge_cmd.finish(
        Message(MessageSegment.music("163", song.id))
        + f"\n{song.name} - {song.artist_text}"
    )

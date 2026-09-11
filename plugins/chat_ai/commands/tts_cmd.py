import base64

from nonebot import on_command, get_plugin_config, get_bot, logger
from nonebot.adapters.onebot.v11 import (
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
)
from nonebot.params import CommandArg

from ..config import Config
from ..state import db
from ..utils.tts import synthesize, TTS_STYLE_KEY

tts_cmd = on_command("朗读", aliases={"read"}, priority=5, block=True)
send_voice_cmd = on_command("发语音", aliases={"sendvoice"}, priority=5, block=True)
voice_style_cmd = on_command("音色", aliases={"语气"}, priority=5, block=True)


@tts_cmd.handle()
async def handle_tts(event: MessageEvent, args: Message = CommandArg()):
    """朗读指定内容：/朗读 <文本>"""
    config = get_plugin_config(Config)

    if not config.tts_enabled:
        await tts_cmd.finish("语音朗读功能未开启")

    text = args.extract_plain_text().strip()
    if not text:
        await tts_cmd.finish("用法：/朗读 <要朗读的内容>")
    if len(text) > config.tts_max_chars:
        await tts_cmd.finish(f"内容太长啦，最多 {config.tts_max_chars} 个字")

    try:
        audio = await synthesize(text, config.tts_instruct)
    except Exception as e:
        logger.error(f"TTS 调用失败: {e}")
        await tts_cmd.finish("语音生成失败，请稍后再试")

    if not audio:
        logger.error("TTS 返回空音频")
        await tts_cmd.finish("语音生成失败，请稍后再试")

    record = MessageSegment.record(f"base64://{base64.b64encode(audio).decode()}")
    if isinstance(event, GroupMessageEvent):
        reply = MessageSegment.reply(event.message_id) + record
    else:
        reply = record

    logger.info(f"TTS 朗读 用户:{event.user_id} 字数:{len(text)}")
    await tts_cmd.finish(reply)


@send_voice_cmd.handle()
async def handle_send_voice(event: MessageEvent, args: Message = CommandArg()):
    """管理员向指定群发语音：/发语音 <群号> <内容> [语气指令]"""
    config = get_plugin_config(Config)

    if not config.tts_enabled:
        await send_voice_cmd.finish("语音朗读功能未开启")
    if event.user_id != config.admin_qq:
        await send_voice_cmd.finish("只有管理员可以使用此命令")

    usage = (
        "用法：/发语音 <群号> <内容> [语气指令]\n"
        "例：/发语音 123456 你好呀 用温柔可爱的语气\n"
        "内容含空格时用 | 分隔内容与语气：/发语音 123456 你好呀 今天天气不错|用开心的语气"
    )

    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await send_voice_cmd.finish(usage)

    group_token, _, rest = arg_text.partition(" ")
    group_token = group_token.strip()
    rest = rest.strip()
    if not group_token.isdigit():
        await send_voice_cmd.finish("群号必须是数字")
    if not rest:
        await send_voice_cmd.finish(usage)
    group_id = int(group_token)

    if "|" in rest:
        content, instruct = (p.strip() for p in rest.split("|", 1))
    else:
        parts = rest.split(maxsplit=1)
        content = parts[0].strip()
        instruct = parts[1].strip() if len(parts) > 1 else ""

    if not content:
        await send_voice_cmd.finish("内容不能为空")
    if len(content) > config.tts_max_chars:
        await send_voice_cmd.finish(f"内容太长啦，最多 {config.tts_max_chars} 个字")

    try:
        audio = await synthesize(content, instruct)
    except Exception as e:
        logger.error(f"TTS 生成失败: {e}")
        await send_voice_cmd.finish("语音生成失败，请稍后再试")

    if not audio:
        await send_voice_cmd.finish("语音生成失败，请稍后再试")

    record = MessageSegment.record(f"base64://{base64.b64encode(audio).decode()}")
    try:
        bot = get_bot()
        await bot.send_group_msg(group_id=group_id, message=Message(record))
    except Exception as e:
        logger.error(f"发送语音到群 {group_id} 失败: {e}")
        await send_voice_cmd.finish(f"发送失败: {e}")

    logger.info(
        f"管理员向群 {group_id} 发送语音 字数:{len(content)} 语气:{instruct or '默认'}"
    )
    await send_voice_cmd.finish(f"已发送语音到群 {group_id}")


@voice_style_cmd.handle()
async def handle_voice_style(event: MessageEvent, args: Message = CommandArg()):
    """查看/设置全局语气口音：/音色 <描述>"""
    config = get_plugin_config(Config)
    arg = args.extract_plain_text().strip()

    if not arg:
        current = (db.get_setting(TTS_STYLE_KEY, "") or "").strip()
        current = current or "（未设置，默认：温柔可爱 + 标准普通话）"
        await voice_style_cmd.finish(
            f"当前全局语气/口音：{current}\n"
            "用法：/音色 <描述>  例：/音色 用台湾腔说话\n"
            "/音色 默认 - 恢复默认"
        )

    if event.user_id != config.admin_qq:
        await voice_style_cmd.finish("只有管理员可以修改全局语气/口音")

    if arg in {"默认", "清除", "恢复", "重置", "reset", "default", "无"}:
        db.set_setting(TTS_STYLE_KEY, "")
        await voice_style_cmd.finish("已恢复默认语气/口音（温柔可爱 + 标准普通话）")

    db.set_setting(TTS_STYLE_KEY, arg)
    await voice_style_cmd.finish(
        f"已设置全局语气/口音：{arg}\n"
        "之后发语音会用「AI 情绪 + 该风格」，且不再强制标准普通话"
    )

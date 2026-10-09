from datetime import datetime, timedelta
from pathlib import Path

from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from .calendar_util import lunar_date_text, solar_date_text, to_lunar
from .tarot_deck import POSITIONS, draw_cards, format_card
from .xiaoliuren import draw_xiaoliuren, format_xiaoliuren

divination_cmd = on_command(
    "今日运势",
    aliases={"塔罗", "塔罗牌", "tarot"},
    priority=5,
    block=True,
)

PROMPT_DIR = Path(__file__).parent.parent.parent / "data" / "md"
TAROT_PROMPT_FILE = PROMPT_DIR / "tarot_prompt.md"
XLR_PROMPT_FILE = PROMPT_DIR / "xiaoliuren_prompt.md"

CACHE_PREFIX = "divination:fortune"

METHOD_TAROT = "tarot"
METHOD_XLR = "xiaoliuren"

TAROT_DEFAULT_PROMPT = (
    "你是一位温和理性的塔罗占卜师。请根据用户给出的三张塔罗牌（现状牌/挑战牌/指引牌）"
    "依次详细解读，并做一段综合总结。不要更改牌面。结尾提醒：塔罗只是趣味娱乐，不构成人生决策建议。"
)
XLR_DEFAULT_PROMPT = (
    "你是一位温和理性的传统术数占卜师。请根据用户给出的小六壬落宫结果，"
    "解读其今日运势与建议。不要更改落宫。结尾提醒：小六壬只是传统趣味娱乐，不构成人生决策建议。"
)

USAGE = (
    "用法：/今日运势 [方式]\n"
    "可选的运势方式：塔罗（默认）、小六壬\n"
    "例如：/今日运势　或　/今日运势 小六壬"
)

TAROT_KEYS = {"", "塔罗", "塔罗牌", "tarot"}
XLR_KEYS = {"小六壬", "六壬", "小六", "xiaoliuren", "xlr"}


def _parse_method(text: str) -> str | None:
    key = text.strip().lower()
    if key in TAROT_KEYS:
        return METHOD_TAROT
    if key in XLR_KEYS:
        return METHOD_XLR
    return None


def _load_prompt(prompt_file: Path, default_prompt: str) -> str:
    try:
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning(f"加载提示词失败 {prompt_file.name}: {e}")
    return default_prompt


def _get_chat_state():
    try:
        from chat_ai import state as chat_state
    except ImportError:
        from plugins.chat_ai import state as chat_state
    return chat_state


def _build(method: str, user_id: int, now) -> tuple[str, str, Path, str]:
    """返回 (发给AI的用户消息, 兜底展示的牌面/落宫, 提示词文件, 默认提示词)。"""
    date_str = now.strftime("%Y%m%d")
    solar_text = solar_date_text(now)

    if method == METHOD_TAROT:
        cards = draw_cards(user_id, date_str)
        detail = "\n".join(
            format_card(card, position) for position, card in zip(POSITIONS, cards)
        )
        user_message = (
            f"今天是阳历 {solar_text}。\n"
            "请结合今天的日期，根据以下抽到的三张塔罗牌进行今日运势解读（请勿更改牌面）：\n"
            + detail
        )
        return user_message, detail, TAROT_PROMPT_FILE, TAROT_DEFAULT_PROMPT

    lunar = to_lunar(now)
    if lunar is not None:
        result = draw_xiaoliuren(user_id, date_str, lunar.month, lunar.day)
        detail = format_xiaoliuren(result, lunar)
        date_line = f"今天是阳历 {solar_text}，对应农历 {lunar_date_text(lunar)}。"
    else:
        # 兜底：无法换算农历时退化使用阳历月/日
        result = draw_xiaoliuren(user_id, date_str, now.month, now.day)
        detail = format_xiaoliuren(result)
        date_line = f"今天是阳历 {solar_text}。"
    user_message = (
        date_line + "\n"
        "请结合今天的日期，根据以下小六壬推演结果进行今日运势解读（请勿更改落宫）：\n"
        + detail
    )
    return user_message, detail, XLR_PROMPT_FILE, XLR_DEFAULT_PROMPT


async def _get_cached(client, key: str) -> str | None:
    if not client:
        return None
    try:
        return await client.get(key)
    except Exception as e:
        logger.warning(f"读取运势缓存失败: {e}")
        return None


async def _set_cached(client, key: str, value: str) -> None:
    if not client:
        return
    try:
        now = datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ttl = int((tomorrow - now).total_seconds())
        await client.setex(key, ttl, value)
    except Exception as e:
        logger.warning(f"写入运势缓存失败: {e}")


@divination_cmd.handle()
async def handle_divination(event: MessageEvent, arg: Message = CommandArg()):
    method = _parse_method(arg.extract_plain_text())
    if method is None:
        await divination_cmd.finish(USAGE)

    user_id = event.user_id
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    cache_key = f"{CACHE_PREFIX}:{method}:{date_str}:{user_id}"

    chat_state = _get_chat_state()

    cached = await _get_cached(chat_state.redis_client, cache_key)
    if cached:
        await divination_cmd.finish(
            MessageSegment.reply(event.message_id) + MessageSegment.text(cached)
        )

    user_message, detail, prompt_file, default_prompt = _build(method, user_id, now)

    if not chat_state.ai_service:
        chat_state.init_ai_service()
    if not chat_state.ai_service:
        await divination_cmd.finish("AI服务暂不可用，请稍后再试~")

    await divination_cmd.send("🔮 正在为你占卜，请稍候……")

    try:
        result = await chat_state.ai_service.chat(
            user_message=user_message,
            system_prompt=_load_prompt(prompt_file, default_prompt),
            max_tokens=900,
            temperature=0.9,
        )
    except Exception as e:
        logger.error(f"运势生成失败: {e}")
        await divination_cmd.finish(f"占卜出错了，请稍后再试~\n\n本次结果：\n{detail}")

    if not result:
        await divination_cmd.finish(f"占卜灵感枯竭了，请稍后再试~\n\n本次结果：\n{detail}")

    await _set_cached(chat_state.redis_client, cache_key, result)

    await divination_cmd.finish(
        MessageSegment.reply(event.message_id) + MessageSegment.text(result)
    )

import base64
import json
import os
import re
from pathlib import Path
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot import logger
from nonebot.typing import T_State

from .config import Config
from .pig_manager import PigManager

config = Config()
pig_manager = PigManager(config)

daily_pig_keyword = on_message(priority=10, block=True)

FORTUNE_PROMPT_FILE = Path(__file__).parent.parent.parent / "data" / "md" / "fortune_prompt.md"


def _load_fortune_prompt() -> str:
    try:
        if FORTUNE_PROMPT_FILE.exists():
            return FORTUNE_PROMPT_FILE.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning(f"加载运势提示词失败: {e}")
    return "你是一个每日运势生成器。请为用户随机生成今日运势。只返回JSON格式：{\"level\":\"等级\",\"detail\":\"说明\"}"


def image_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def build_pig_msg(name: str, img_path: str, explan: str, reply_msg_id: int, fortune: dict | None = None) -> Message:
    b64 = image_to_base64(img_path)
    pig_name = os.path.splitext(name)[0]
    msg = Message()
    msg += MessageSegment.reply(reply_msg_id)
    msg += MessageSegment.text("🎉 抓到一只新猪猪啦！\n")
    msg += MessageSegment.image(f"base64://{b64}")
    msg += MessageSegment.text(f"{pig_name}\n{explan}")

    if fortune and fortune.get("level") and fortune.get("detail"):
        msg += MessageSegment.text(f"\n🔮 今日运势：{fortune['level']}\n{fortune['detail']}")

    return msg


async def generate_fortune() -> dict | None:
    """调用AI生成每日运势，失败返回None"""
    try:
        try:
            from chat_ai.state import ai_service, init_ai_service
        except ImportError:
            from plugins.chat_ai.state import ai_service, init_ai_service

        if not ai_service:
            init_ai_service()
        if not ai_service:
            logger.warning("AI服务未初始化，跳过运势生成")
            return None

        response = await ai_service.chat(
            user_message="请生成今日运势",
            system_prompt=_load_fortune_prompt(),
            max_tokens=200,
            temperature=1.2,
        )

        if not response:
            return None

        # 尝试解析JSON
        try:
            # 先尝试直接解析
            result = json.loads(response.strip())
            if "level" in result and "detail" in result:
                return result
        except json.JSONDecodeError:
            pass

        # 尝试从文本中提取JSON
        match = re.search(r'\{[^}]*"level"[^}]*"detail"[^}]*\}', response)
        if match:
            try:
                result = json.loads(match.group())
                if "level" in result and "detail" in result:
                    return result
            except json.JSONDecodeError:
                pass

        # 兜底：用正则提取等级
        level_match = re.search(r'(大吉|中吉|小吉|吉|末吉|凶|大凶)', response)
        if level_match:
            level = level_match.group(1)
            # 去掉等级部分，剩下的作为detail
            detail = re.sub(r'(大吉|中吉|小吉|吉|末吉|凶|大凶)[：:\s]*', '', response).strip()
            if detail:
                return {"level": level, "detail": detail}

        logger.warning(f"AI运势返回格式异常: {response[:200]}")
        return None

    except Exception as e:
        logger.error(f"生成运势失败: {e}")
        return None


@daily_pig_keyword.handle()
async def handle_daily_pig(bot: Bot, event: GroupMessageEvent, state: T_State):
    if event.get_plaintext().strip() != "每日猪猪":
        await daily_pig_keyword.skip()
    group_id = event.group_id
    sender_id = event.user_id
    msg_id = event.message_id

    cached_pig = pig_manager.get_daily_pig(sender_id, group_id)
    if cached_pig:
        name = cached_pig.get("name")
        img_path = cached_pig.get("img_path")
        explan = cached_pig.get("explan")
        fortune = cached_pig.get("fortune")
        if name and img_path and explan:
            await daily_pig_keyword.finish(build_pig_msg(name, img_path, explan, msg_id, fortune))
        else:
            await daily_pig_keyword.finish("缓存数据异常，请稍后再试~")

    pig_data = pig_manager.get_random_pig()
    if not pig_data:
        await daily_pig_keyword.finish("猪猪库为空，请联系管理员~")

    # 生成运势并存入缓存
    fortune = await generate_fortune()
    if fortune:
        pig_data["fortune"] = fortune

    pig_manager.set_daily_pig(sender_id, group_id, pig_data)

    name = pig_data.get("name")
    img_path = pig_data.get("img_path")
    explan = pig_data.get("explan")
    if name and img_path and explan:
        await daily_pig_keyword.finish(build_pig_msg(name, img_path, explan, msg_id, fortune))
    else:
        await daily_pig_keyword.finish("猪猪数据异常，请稍后再试~")

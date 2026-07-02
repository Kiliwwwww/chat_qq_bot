from pathlib import Path
from nonebot import on_command, on_message, get_plugin_config, require
from nonebot.adapters.onebot.v11 import MessageEvent, Message, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.exception import FinishedException
from nonebot import logger

from .config import Config
from .service import AIService
from .database import Database

# 依赖 localstore 插件
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

# 提示词文件路径
PROMPT_FILE = Path(__file__).parent.parent.parent / "data" / "md" / "system_prompt.md"

# 存储用户对话历史和AI服务实例
user_histories: dict[int, list[dict[str, str]]] = {}
ai_service: AIService = None

# 初始化数据库
db = Database(get_plugin_data_file("chat_ai.db"))


def init_ai_service():
    """初始化AI服务"""
    global ai_service
    try:
        config = get_plugin_config(Config)
        system_prompt = AIService.load_prompt_from_file(PROMPT_FILE) or config.ai_system_prompt
        ai_service = AIService(
            api_key=config.ai_api_key,
            base_url=config.ai_base_url,
            model=config.ai_model,
            max_tokens=config.ai_max_tokens,
            temperature=config.ai_temperature,
            top_p=config.ai_top_p,
            system_prompt=system_prompt,
        )
        logger.info("AI 服务初始化完成")
    except Exception as e:
        logger.error(f"AI 服务初始化失败: {e}")


# 注册命令处理器
reset_cmd = on_command("reset", aliases={"重置对话"}, priority=5, block=True)
settings_cmd = on_command("settings", aliases={"设置"}, priority=5, block=True)

# 私聊消息处理器（优先级较低，在命令之后处理）
private_msg = on_message(priority=10, block=True)


@settings_cmd.handle()
async def handle_settings(event: MessageEvent, args: Message = CommandArg()):
    """处理设置命令"""
    arg = args.extract_plain_text().strip()

    if not arg:
        # 显示当前白名单
        allowed_users = db.get_all_users()
        if allowed_users:
            user_list = "\n".join([str(uid) for uid in sorted(allowed_users)])
            await settings_cmd.finish(f"当前允许的用户:\n{user_list}")
        else:
            await settings_cmd.finish("当前没有允许的用户，使用 /settings <QQ号> 添加")

    # 解析 QQ 号
    try:
        qq_id = int(arg)
    except ValueError:
        await settings_cmd.finish("请输入有效的 QQ 号")

    # 添加或移除白名单
    if db.user_exists(qq_id):
        db.remove_user(qq_id)
        await settings_cmd.finish(f"已移除用户 {qq_id}")
    else:
        db.add_user(qq_id)
        await settings_cmd.finish(f"已添加用户 {qq_id}")


@private_msg.handle()
async def handle_private_msg(event: MessageEvent):
    """处理私聊消息"""
    # 只处理私聊消息，群聊放行
    if not isinstance(event, PrivateMessageEvent):
        await private_msg.skip()

    # 非白名单用户放行
    if not db.user_exists(event.user_id):
        await private_msg.skip()

    if not ai_service:
        init_ai_service()

    # AI 服务未初始化放行
    if not ai_service:
        await private_msg.skip()

    user_message = event.get_plaintext().strip()

    # 忽略空消息或命令
    if not user_message or user_message.startswith("/"):
        await private_msg.skip()

    user_id = event.user_id

    # 获取用户历史记录
    if user_id not in user_histories:
        user_histories[user_id] = []

    # 添加用户消息到历史
    user_histories[user_id].append({
        "role": "user",
        "content": user_message,
    })

    try:
        # 调用 AI 服务
        reply = ai_service.chat_with_history(
            messages=user_histories[user_id],
        )

        # 添加助手回复到历史
        user_histories[user_id].append({
            "role": "assistant",
            "content": reply,
        })

        # 限制历史记录长度（保留最近 10 轮对话）
        if len(user_histories[user_id]) > 20:
            user_histories[user_id] = user_histories[user_id][-20:]

        await private_msg.finish(reply)

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        await private_msg.finish(f"AI 调用失败: {e}")


@reset_cmd.handle()
async def handle_reset(event: MessageEvent):
    """重置用户对话历史"""
    user_id = event.user_id

    if user_id in user_histories:
        del user_histories[user_id]
        await reset_cmd.finish("对话历史已重置")
    else:
        await reset_cmd.finish("没有对话历史需要重置")

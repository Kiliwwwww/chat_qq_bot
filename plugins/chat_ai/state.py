from pathlib import Path

import redis.asyncio as aioredis
from nonebot import get_plugin_config, require
from nonebot import logger

from .config import Config
from .service import AIService
from .ragflow_client import RagFlowClient
from .database import Database

# 依赖 localstore 插件
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

# 提示词文件路径
PROMPT_FILE = Path(__file__).parent.parent.parent / "data" / "md" / "system_prompt.md"
PROMPT_KIND_FILE = Path(__file__).parent.parent.parent / "data" / "md" / "system_prompt_kind.md"

# 当前提示词模式：default=默认（雌小鬼），kind=邻家大姐姐
current_prompt_mode: str = "default"

# 禁言状态：bot_mute_until 存储禁言到期时间戳
bot_mute_until: float = 0

# 需要自动贴表情的用户集合 {(group_id, user_id)}
auto_emoji_users: set[tuple[int, int]] = set()

# 需要在所有群自动贴表情的用户集合 {user_id}
auto_emoji_all_groups_users: set[int] = set()

# 开启全体贴表情的群集合 {group_id}
auto_emoji_groups: set[int] = set()

# 存储用户对话历史和AI服务实例
user_histories: dict[int, list[dict[str, str]]] = {}
group_histories: dict[int, list[dict[str, str]]] = {}
group_last_reply: dict[int, float] = {}  # 群最后回复时间戳
group_recent_messages: dict[int, list[tuple[int, str]]] = {}  # 群最近消息 [(user_id, message)]
group_last_repeated: dict[int, str] = {}  # 群最后复读的消息内容
ai_service: AIService = None
ragflow_client: RagFlowClient = None

# Redis 客户端
redis_client: aioredis.Redis = None

# 初始化数据库
db = Database(get_plugin_data_file("chat_ai.db"))

# 从数据库加载群欢迎语
group_welcome_messages: dict[int, str] = db.get_all_welcome_messages()


def init_ai_service():
    """初始化AI服务"""
    global ai_service, ragflow_client, current_prompt_mode, redis_client
    try:
        config = get_plugin_config(Config)
        # 从数据库读取人格模式
        current_prompt_mode = db.get_setting("prompt_mode", "default")
        # 根据当前模式选择提示词文件
        prompt_file = PROMPT_KIND_FILE if current_prompt_mode == "kind" else PROMPT_FILE
        system_prompt = AIService.load_prompt_from_file(prompt_file) or config.ai_system_prompt
        # 替换提示词中的管理员QQ号和昵称占位符
        if system_prompt:
            system_prompt = system_prompt.replace("{admin_qq}", str(config.admin_qq))
            system_prompt = system_prompt.replace("{admin_name}", config.admin_name)
        ai_service = AIService(
            api_key=config.ai_api_key,
            base_url=config.ai_base_url,
            model=config.ai_model,
            max_tokens=config.ai_max_tokens,
            temperature=config.ai_temperature,
            top_p=config.ai_top_p,
            system_prompt=system_prompt,
            debug_log=config.ai_debug_log,
        )
        
        # 初始化 RAGFlow 客户端
        if config.ragflow_enabled and config.ragflow_api_key:
            ragflow_client = RagFlowClient(
                base_url=config.ragflow_base_url,
                api_key=config.ragflow_api_key,
                kb_ids=config.ragflow_kb_ids,
                top_k=config.ragflow_top_k,
            )
            logger.info(f"RAGFlow 客户端初始化完成，知识库数量: {len(config.ragflow_kb_ids)}")
        else:
            ragflow_client = None
            logger.info("RAGFlow 未启用或未配置 API Key，跳过初始化")
        
        # 构建 Redis URL
        redis_url = f"redis://"
        if config.redis_password:
            redis_url += f":{config.redis_password}@"
        redis_url += f"{config.redis_host}:{config.redis_port}/{config.redis_db}"
        
        # 初始化 Redis 连接
        redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
            retry_on_timeout=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        logger.info(f"Redis 连接初始化完成: {redis_url}")
        
        logger.info(f"AI 服务初始化完成，当前人格模式: {current_prompt_mode}")
    except Exception as e:
        logger.error(f"AI 服务初始化失败: {e}")


async def get_group_history(group_id: int) -> list[dict[str, str]]:
    """从 Redis 获取群聊历史记录"""
    if not redis_client:
        return group_histories.get(group_id, [])
    
    config = get_plugin_config(Config)
    key = f"{config.redis_key_prefix}group:{group_id}"
    try:
        data = await redis_client.get(key)
        if data:
            import json
            return json.loads(data)
    except Exception as e:
        logger.warning(f"从 Redis 获取群聊历史失败，使用内存缓存: {e}")
        # 尝试重新连接
        try:
            await redis_client.ping()
        except Exception:
            pass
    
    return group_histories.get(group_id, [])


async def set_group_history(group_id: int, history: list[dict[str, str]]):
    """将群聊历史记录存储到 Redis"""
    # 始终更新内存缓存
    group_histories[group_id] = history
    
    if not redis_client:
        return
    
    config = get_plugin_config(Config)
    key = f"{config.redis_key_prefix}group:{group_id}"
    try:
        import json
        await redis_client.set(key, json.dumps(history, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"存储群聊历史到 Redis 失败，已缓存到内存: {e}")


async def get_user_history(user_id: int) -> list[dict[str, str]]:
    """从 Redis 获取私聊历史记录"""
    if not redis_client:
        return user_histories.get(user_id, [])
    
    config = get_plugin_config(Config)
    key = f"{config.redis_key_prefix}user:{user_id}"
    try:
        data = await redis_client.get(key)
        if data:
            import json
            return json.loads(data)
    except Exception as e:
        logger.warning(f"从 Redis 获取私聊历史失败，使用内存缓存: {e}")
        try:
            await redis_client.ping()
        except Exception:
            pass
    
    return user_histories.get(user_id, [])


async def set_user_history(user_id: int, history: list[dict[str, str]]):
    """将私聊历史记录存储到 Redis"""
    # 始终更新内存缓存
    user_histories[user_id] = history
    
    if not redis_client:
        return
    
    config = get_plugin_config(Config)
    key = f"{config.redis_key_prefix}user:{user_id}"
    try:
        import json
        await redis_client.set(key, json.dumps(history, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"存储私聊历史到 Redis 失败，已缓存到内存: {e}")


async def delete_group_history(group_id: int):
    """删除群聊历史记录"""
    if redis_client:
        config = get_plugin_config(Config)
        key = f"{config.redis_key_prefix}group:{group_id}"
        try:
            await redis_client.delete(key)
        except Exception as e:
            logger.error(f"从 Redis 删除群聊历史失败: {e}")
    
    if group_id in group_histories:
        del group_histories[group_id]


async def delete_user_history(user_id: int):
    """删除私聊历史记录"""
    if redis_client:
        config = get_plugin_config(Config)
        key = f"{config.redis_key_prefix}user:{user_id}"
        try:
            await redis_client.delete(key)
        except Exception as e:
            logger.error(f"从 Redis 删除私聊历史失败: {e}")
    
    if user_id in user_histories:
        del user_histories[user_id]

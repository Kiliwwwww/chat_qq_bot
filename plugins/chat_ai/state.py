from pathlib import Path

from nonebot import get_plugin_config, require
from nonebot import logger

from .config import Config
from .service import AIService
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

# 初始化数据库
db = Database(get_plugin_data_file("chat_ai.db"))

# 从数据库加载群欢迎语
group_welcome_messages: dict[int, str] = db.get_all_welcome_messages()


def init_ai_service():
    """初始化AI服务"""
    global ai_service, current_prompt_mode
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
        logger.info(f"AI 服务初始化完成，当前人格模式: {current_prompt_mode}")
    except Exception as e:
        logger.error(f"AI 服务初始化失败: {e}")

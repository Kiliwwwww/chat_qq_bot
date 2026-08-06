"""全局状态单例：配置、数据库、缓存实例。"""

from nonebot import get_plugin_config, require, logger

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

from .config import Config
from .cache import Cache
from .database import Database

# 插件配置
config = get_plugin_config(Config)

# 数据库（SQLite，按群隔离）
db = Database(get_plugin_data_file("xiuxian.db"))

# Redis 缓存（初始化延迟到应用启动时）
_cache = Cache(prefix=config.redis_key_prefix)


def init_cache(redis_client) -> None:
    """在应用启动时注入 Redis 客户端"""
    global _cache
    _cache = Cache(redis_client=redis_client, prefix=config.redis_key_prefix)
    logger.info(f"修仙插件 Redis 缓存初始化完成，可用: {_cache.is_available()}")


def get_cache() -> Cache:
    """获取缓存实例（Redis 不可用时自动使用内存缓存）"""
    return _cache

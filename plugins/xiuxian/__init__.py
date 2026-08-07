"""QQ 群修仙挂机游戏插件。

插件结构：
- config.py    配置
- constants.py 游戏静态数据（境界/灵根/功法/物品/事件等）
- database.py  SQLite 持久化（所有表按 group_id 群隔离）
- cache.py     Redis 缓存（不可用时降级内存）
- state.py     全局单例
- services/    业务逻辑层
- commands/    指令层
"""

import redis.asyncio as aioredis
from nonebot import get_driver, get_plugin_config, logger

from .config import Config
from .state import init_cache
from .services.world import start_world_scheduler
from .commands import (  # noqa: F401  导入以注册指令
    xiuxian_cmd,
    random_fate_cmd,
    trash_fate_cmd,
    status_cmd,
    help_cmd,
    change_physique_cmd,
    rebirth_cmd,
    suicide_cmd,
    game_on_cmd,
    game_off_cmd,
    biguan_cmd,
    chuguan_cmd,
    tupo_cmd,
    tansuo_cmd,
    gongfa_cmd,
    learn_gongfa_cmd,
    catalog_cmd,
    upgrade_gongfa_cmd,
    world_cmd,
    trigger_event_cmd,
    summon_merchant_cmd,
    lian_dan_cmd,
    lian_qi_cmd,
    inventory_cmd,
    equip_cmd,
    unequip_cmd,
    gift_cmd,
    pet_cmd,
    feed_cmd,
    pet_shop_cmd,
    pet_shop_buy_cmd,
    plant_cmd,
    harvest_cmd,
    field_cmd,
    use_pill_cmd,
    shop_cmd,
    shop_buy_cmd,
    shop_sell_cmd,
    market_cmd,
    market_sell_cmd,
    market_buy_cmd,
    market_buy_merchant_cmd,
    market_buy_breakthrough_cmd,
    market_cancel_cmd,
    capture_cmd,
    furnace_cmd,
    escape_cmd,
    release_cmd,
    xiuxiu_cmd,
    signup_cmd,
    battle_status_cmd,
    pk_cmd,
    duel_challenge_cmd,
    duel_accept_cmd,
    boss_attack_cmd,
    boss_status_cmd,
    boss_spawn_cmd,
    invasion_attack_cmd,
    invasion_status_cmd,
    ranking_cmd,
)

driver = get_driver()
config = get_plugin_config(Config)


def _build_redis_url(cfg: Config) -> str:
    url = "redis://"
    if cfg.redis_password:
        url += f":{cfg.redis_password}@"
    url += f"{cfg.redis_host}:{cfg.redis_port}/{cfg.redis_db}"
    return url


@driver.on_startup
async def _on_startup() -> None:
    """应用启动时初始化 Redis 缓存与世界 Tick 任务"""
    redis_client = None
    try:
        redis_client = aioredis.from_url(
            _build_redis_url(config),
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
            retry_on_timeout=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await redis_client.ping()
        logger.info("修仙插件 Redis 连接成功")
    except Exception as e:
        logger.error(f"修仙插件 Redis 连接失败（将使用内存缓存）: {e}")
        redis_client = None

    init_cache(redis_client)
    start_world_scheduler()


__all__ = [  # 导出指令，保证 NoneBot 注册
    "xiuxian_cmd",
    "random_fate_cmd",
    "trash_fate_cmd",
    "status_cmd",
    "help_cmd",
    "change_physique_cmd",
    "rebirth_cmd",
    "suicide_cmd",
    "game_on_cmd",
    "game_off_cmd",
    "biguan_cmd",
    "chuguan_cmd",
    "tupo_cmd",
    "tansuo_cmd",
    "gongfa_cmd",
    "learn_gongfa_cmd",
    "catalog_cmd",
    "upgrade_gongfa_cmd",
    "world_cmd",
    "trigger_event_cmd",
    "summon_merchant_cmd",
    "lian_dan_cmd",
    "lian_qi_cmd",
    "inventory_cmd",
    "equip_cmd",
    "unequip_cmd",
    "gift_cmd",
    "pet_cmd",
    "feed_cmd",
    "pet_shop_cmd",
    "pet_shop_buy_cmd",
    "plant_cmd",
    "harvest_cmd",
    "field_cmd",
    "use_pill_cmd",
    "shop_cmd",
    "shop_buy_cmd",
    "shop_sell_cmd",
    "market_cmd",
    "market_sell_cmd",
    "market_buy_cmd",
    "market_buy_merchant_cmd",
    "market_buy_breakthrough_cmd",
    "market_cancel_cmd",
    "capture_cmd",
    "furnace_cmd",
    "escape_cmd",
    "release_cmd",
    "xiuxiu_cmd",
    "signup_cmd",
    "battle_status_cmd",
    "pk_cmd",
    "duel_challenge_cmd",
    "duel_accept_cmd",
    "boss_attack_cmd",
    "boss_status_cmd",
    "boss_spawn_cmd",
    "invasion_attack_cmd",
    "invasion_status_cmd",
    "ranking_cmd",
]

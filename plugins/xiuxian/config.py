from pydantic import BaseModel


class Config(BaseModel):
    """修仙挂机游戏配置类"""

    # 管理员 QQ 号（只有此人可在群内执行「开启修仙」/「关闭修仙」）
    admin_qq: int = 1154798056

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_key_prefix: str = "xiuxian:"

    # 世界 Tick 间隔（秒），世界状态推进周期
    world_tick_interval: int = 60

    # 世界事件切换间隔（分钟），事件持续时长
    world_event_duration: int = 180

    # 管理员手动触发事件的持续时长（分钟）
    trigger_event_duration: int = 30

    # 神秘商人出现间隔（分钟）
    merchant_interval: int = 120

    # 突破商人停留时长（分钟）
    breakthrough_merchant_duration: int = 60

    # 探索冷却时间（秒）
    explore_cooldown: int = 20

    # 闭关达到该时长（分钟）出关后可回满血量
    cultivation_heal_minutes: int = 5

    # 突破失败损失修为比例
    breakthrough_fail_penalty: float = 0.2

    # 弟子数量上限
    max_furnace: int = 3

    # 传功冷却时间（分钟）
    xiuxiu_cooldown_minutes: int = 10

    # 闭关超过该小时数，出关时可能走火入魔
    zouhuo_cultivate_hours: float = 6.0

    # 学习新功法的灵石费用（境界越高越贵，此为基础值）
    learn_gongfa_cost: int = 100

    # 升级功法熟练度的基础灵石费用（随熟练度等级与境界增长）
    gongfa_upgrade_cost_base: int = 200

    # 更换体质的基础灵石费用（按境界翻倍，指定目标体质为基础费用的 3 倍）
    change_physique_cost: int = 5000

    # 转世重生：达到该境界索引才可转世（2=金丹）
    rebirth_min_realm: int = 2

    # 每次转世获得的气运加成
    rebirth_fortune_bonus: int = 500

    # 每次转世获得的永久修炼速率加成（每次 +5%）
    rebirth_rate_bonus: float = 0.05

    # 转世后回到的初始灵石
    rebirth_coin: int = 100

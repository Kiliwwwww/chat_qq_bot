import redis
from datetime import datetime
from nonebot import logger

from .config import Config


class PairingManager:
    """配对管理器，使用Redis存储配对关系"""
    
    def __init__(self, config: Config):
        self.redis_client = None
        try:
            self.redis_client = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                password=config.redis_password if config.redis_password else None,
                decode_responses=config.redis_decode_responses,
            )
            self.redis_client.ping()
            logger.info("Daily Wife Redis 连接成功")
        except Exception as e:
            logger.error(f"Daily Wife Redis 连接失败: {e}，配对功能将不可用")
            self.redis_client = None
    
    def _get_pairing_key(self) -> str:
        """获取全局配对的Redis key"""
        return "daily_wife:pairing"
    
    def _get_daily_result_key(self, user_id: int, group_id: int) -> str:
        """获取每日结果的Redis key（包含日期和群ID）"""
        today = datetime.now().strftime("%Y%m%d")
        return f"daily_wife:result:{today}:{group_id}:{user_id}"
    
    def set_pairing(self, user_id: int, wife_id: int) -> bool:
        """设置全局配对关系（所有群生效）"""
        if self.redis_client is None:
            return False
        try:
            key = self._get_pairing_key()
            self.redis_client.hset(key, str(user_id), str(wife_id))
            return True
        except Exception as e:
            logger.error(f"设置配对失败: {e}")
            return False
    
    def get_pairing(self, user_id: int) -> int | None:
        """获取配对关系，返回配对的用户ID"""
        if self.redis_client is None:
            return None
        try:
            key = self._get_pairing_key()
            wife_id = self.redis_client.hget(key, str(user_id))
            return int(wife_id) if wife_id else None
        except Exception as e:
            logger.error(f"获取配对失败: {e}")
            return None
    
    def remove_pairing(self, user_id: int) -> bool:
        """删除配对关系"""
        if self.redis_client is None:
            return False
        try:
            key = self._get_pairing_key()
            self.redis_client.hdel(key, str(user_id))
            return True
        except Exception as e:
            logger.error(f"删除配对失败: {e}")
            return False
    
    def get_daily_result(self, user_id: int, group_id: int) -> int | None:
        """获取用户指定群今日的老婆结果"""
        if self.redis_client is None:
            return None
        try:
            key = self._get_daily_result_key(user_id, group_id)
            wife_id = self.redis_client.get(key)
            return int(wife_id) if wife_id else None
        except Exception as e:
            logger.error(f"获取每日结果失败: {e}")
            return None
    
    def set_daily_result(self, user_id: int, wife_id: int, group_id: int) -> bool:
        """保存用户指定群今日的老婆结果（24小时后过期）"""
        if self.redis_client is None:
            return False
        try:
            key = self._get_daily_result_key(user_id, group_id)
            # 设置86400秒（24小时）后过期
            self.redis_client.setex(key, 86400, str(wife_id))
            return True
        except Exception as e:
            logger.error(f"保存每日结果失败: {e}")
            return False
    
    def _get_daily_children_key(self, user_id: int, group_id: int) -> str:
        """获取每日孩子列表的Redis key（包含日期和群ID）"""
        today = datetime.now().strftime("%Y%m%d")
        return f"daily_wife:children:{today}:{group_id}:{user_id}"
    
    def get_daily_children(self, user_id: int, group_id: int) -> list[int]:
        """获取用户今日的孩子列表"""
        if self.redis_client is None:
            return []
        try:
            key = self._get_daily_children_key(user_id, group_id)
            children = self.redis_client.lrange(key, 0, -1)
            return [int(c) for c in children]
        except Exception as e:
            logger.error(f"获取孩子列表失败: {e}")
            return []
    
    def add_daily_child(self, user_id: int, group_id: int, child_id: int) -> bool:
        """添加一个孩子到今日孩子列表（最多3个）"""
        if self.redis_client is None:
            return False
        try:
            key = self._get_daily_children_key(user_id, group_id)
            # 检查是否已经有3个孩子
            current_count = self.redis_client.llen(key)
            if current_count >= 3:
                return False
            # 添加孩子并设置过期时间
            self.redis_client.rpush(key, str(child_id))
            self.redis_client.expire(key, 86400)  # 24小时过期
            return True
        except Exception as e:
            logger.error(f"添加孩子失败: {e}")
            return False

    def get_leaderboard_users(self, group_id: int, days: int = 2) -> list[int]:
        """从排行榜缓存中获取最近几天所有上过榜的用户（按发言总数排序）

        Args:
            group_id: 群号
            days: 统计最近几天（含今天），默认2天

        Returns:
            用户ID列表，按总发言数从高到低排序
        """
        if self.redis_client is None:
            return []
        try:
            today = datetime.now().strftime("%Y%m%d")
            keys = [f"ranking:group:{group_id}:{today}"]
            if days > 1:
                from datetime import timedelta
                for i in range(1, days):
                    day = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                    keys.append(f"ranking:group:{group_id}:{day}")

            # 汇总最近几天的发言总数
            user_counts: dict[int, int] = {}
            for key in keys:
                all_users = self.redis_client.hgetall(key)
                if not all_users:
                    continue
                for uid, count in all_users.items():
                    user_counts[int(uid)] = user_counts.get(int(uid), 0) + int(count)

            sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
            return [uid for uid, _ in sorted_users]
        except Exception as e:
            logger.error(f"获取排行榜失败: {e}")
            return []

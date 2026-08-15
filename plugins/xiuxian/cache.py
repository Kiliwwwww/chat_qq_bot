"""Redis 缓存层。

封装常用缓存操作，Redis 不可用时自动降级为内存缓存，保证游戏功能不中断。
"""

import json
import time
from typing import Any, Optional

from nonebot import logger


class Cache:
    """缓存管理类"""

    def __init__(self, redis_client=None, prefix: str = "xiuxian:"):
        self.redis = redis_client
        self.prefix = prefix
        self._memory: dict[str, tuple[Any, float]] = {}

    # ==================== 基础操作 ====================

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def is_available(self) -> bool:
        return self.redis is not None

    async def get(self, key: str) -> Optional[Any]:
        """获取 JSON 缓存"""
        if self.redis:
            try:
                data = await self.redis.get(self._key(key))
                if data is not None:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis 读取失败 {key}: {e}")
        return self._memory_get(key)

    async def set(self, key: str, value: Any, expire: int = 300) -> None:
        """写入 JSON 缓存（默认 5 分钟过期）"""
        if self.redis:
            try:
                await self.redis.set(self._key(key), json.dumps(value, ensure_ascii=False), ex=expire)
            except Exception as e:
                logger.warning(f"Redis 写入失败 {key}: {e}")
        self._memory_set(key, value, expire)

    async def delete(self, key: str) -> None:
        if self.redis:
            try:
                await self.redis.delete(self._key(key))
            except Exception as e:
                logger.warning(f"Redis 删除失败 {key}: {e}")
        self._memory.pop(self._key(key), None)

    # ==================== 数值操作 ====================

    async def hset(self, name: str, field: str, value: Any) -> None:
        if self.redis:
            try:
                await self.redis.hset(self._key(name), field, value)
            except Exception as e:
                logger.warning(f"Redis hset 失败 {name}: {e}")
        # 内存降级：存到 name:field 键
        self._memory_set(f"{name}:{field}", value, 300)

    async def hget(self, name: str, field: str) -> Optional[Any]:
        if self.redis:
            try:
                value = await self.redis.hget(self._key(name), field)
                if value is not None:
                    return value
            except Exception as e:
                logger.warning(f"Redis hget 失败 {name}: {e}")
        return self._memory_get(f"{name}:{field}")

    async def hgetall(self, name: str) -> dict:
        if self.redis:
            try:
                return await self.redis.hgetall(self._key(name))
            except Exception as e:
                logger.warning(f"Redis hgetall 失败 {name}: {e}")
        return {}

    # ==================== 内存降级 ====================

    def _memory_get(self, key: str) -> Optional[Any]:
        item = self._memory.get(self._key(key))
        if item is None:
            return None
        value, expire_at = item
        if expire_at and time.time() > expire_at:
            self._memory.pop(self._key(key), None)
            return None
        return value

    def _memory_set(self, key: str, value: Any, expire: int = 300) -> None:
        self._memory[self._key(key)] = (value, time.time() + expire if expire else 0)

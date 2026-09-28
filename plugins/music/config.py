import os
from pydantic import BaseModel


class Config(BaseModel):
    # 搜索返回的最大候选数
    music_search_limit: int = int(os.getenv("music_search_limit", "5"))
    # 点歌候选缓存有效期（秒），超时后需重新点歌才能选歌
    music_cache_ttl: int = int(os.getenv("music_cache_ttl", "300"))

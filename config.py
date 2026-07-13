from pydantic import BaseModel


class RedisConfig(BaseModel):
    """Redis 配置类"""
    
    # Redis 连接配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_decode_responses: bool = True


class GlobalConfig(BaseModel):
    """全局配置类"""
    
    # Redis 配置
    redis: RedisConfig = RedisConfig()
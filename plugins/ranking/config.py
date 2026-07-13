from pydantic import BaseModel


class Config(BaseModel):
    """排行榜配置类"""
    
    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_decode_responses: bool = True
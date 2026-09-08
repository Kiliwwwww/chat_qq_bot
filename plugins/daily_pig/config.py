import os
from pydantic import BaseModel


class Config(BaseModel):
    # Redis 配置
    redis_host: str = os.getenv("redis_host", "host.docker.internal")
    redis_port: int = int(os.getenv("redis_port", "6379"))
    redis_db: int = int(os.getenv("redis_db", "0"))
    redis_password: str = os.getenv("redis_password", "infini_rag_flow")
    redis_decode_responses: bool = os.getenv("redis_decode_responses", "true").lower() == "true"

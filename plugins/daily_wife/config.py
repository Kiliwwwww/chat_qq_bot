from pydantic import BaseModel


class Config(BaseModel):
    # 头像大小（像素）
    avatar_size: int = 200
    # 图片宽度
    image_width: int = 900
    # 图片高度
    image_height: int = 650
    # 是否允许抽到自己（默认不允许）
    allow_self: bool = False
    # 排行榜用户权重（优先级高于普通群友）
    leaderboard_weight: int = 5
    # 普通群友权重
    normal_weight: int = 1
    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_decode_responses: bool = True

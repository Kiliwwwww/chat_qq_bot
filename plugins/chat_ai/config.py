from pydantic import BaseModel


class Config(BaseModel):
    """AI 配置类"""
    
    # API 配置
    ai_api_key: str = ""
    ai_base_url: str = "https://api.xiaomimimo.com/v1"
    ai_model: str = "mimo-v2.5"
    
    # 生成参数
    ai_max_tokens: int = 1024
    ai_temperature: float = 1.0
    ai_top_p: float = 0.95
    
    # 管理员QQ号
    admin_qq: int = 1154798056
    
    # 管理员昵称
    admin_name: str = "宝宝葵"
    
    # 群消息回复概率 (0.0~1.0)
    group_reply_chance: float = 0.3
    
    # 随机复读群友消息概率 (0.0~1.0)
    random_repeat_chance: float = 0.03
    
    # 调试日志开关
    ai_debug_log: bool = False
    
    # 系统提示词
    ai_system_prompt: str = (
        "You are MiMo, an AI assistant developed by Xiaomi. "
        "Today is date: Tuesday, December 16, 2025. "
        "Your knowledge cutoff date is December 2024."
    )

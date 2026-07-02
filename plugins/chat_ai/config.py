from pydantic import BaseModel


class Config(BaseModel):
    """AI 配置类"""
    
    # API 配置
    ai_api_key: str = ""
    ai_base_url: str = "https://api.xiaomimimo.com/v1"
    ai_model: str = "mimo-v2.5-pro"
    
    # 生成参数
    ai_max_tokens: int = 1024
    ai_temperature: float = 1.0
    ai_top_p: float = 0.95
    
    # 系统提示词
    ai_system_prompt: str = (
        "You are MiMo, an AI assistant developed by Xiaomi. "
        "Today is date: Tuesday, December 16, 2025. "
        "Your knowledge cutoff date is December 2024."
    )

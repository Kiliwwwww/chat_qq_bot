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
    
    # 上下文历史记录条数
    ai_context_limit: int = 50

    # 历史记录里的图片是否清理
    # False（默认）：最近 ai_context_limit 条消息里的图片都保留并发给 AI
    # True：只保留最新一条消息的图片，更早的图片退化成纯文本
    history_image_clean_enabled: bool = False
    
    # 管理员QQ号
    admin_qq: int = 1154798056
    
    # 管理员昵称
    admin_name: str = "宝宝葵"
    
    # 群消息回复概率 (0.0~1.0)
    group_reply_chance: float = 0.05

    # 对话延续：机器人刚说完话，被它搭话的人紧接着直接回一句（既没@、也没引用），
    # 中间也没被群里其他人插话，就按"在跟机器人说话"处理，不用每次重新@
    group_follow_up_enabled: bool = True
    # 延续判定时间窗口（秒）
    group_follow_up_window: float = 60.0
    # 延续消息的回复概率 (0.0~1.0)，1.0 表示一定接话
    group_follow_up_chance: float = 1.0
    
    # 随机复读群友消息概率 (0.0~1.0)
    random_repeat_chance: float = 0.03
    
    # 连发消息：允许 AI 判断是否需要多回几句（在主回复之外补发消息）
    multi_message_enabled: bool = True
    # 连发时单轮最多发送的消息总条数（含主回复）
    multi_message_max: int = 3
    # 关键词强制连发：群友明确要求"多说几句"时固定连发
    multi_message_force_enabled: bool = True
    # 强制连发时的随机条数范围（含主回复）
    multi_message_force_min: int = 2
    multi_message_force_max: int = 3
    
    # 全体贴表情概率 (0.0~1.0)
    group_emoji_chance: float = 0.3
    
    # 全局贴表情的emoji_id
    global_emoji_id: int = 46

    # 主动冒泡配置
    bubble_enabled: bool = True
    bubble_idle_minutes: int = 30
    bubble_cooldown_minutes: int = 180
    bubble_chance: float = 0.5
    bubble_ai_enabled: bool = True

    # 今日新闻（微博热搜 + 知乎热榜，推送到 groupsettings 里的所有群）
    daily_news_enabled: bool = True
    # 每天早上几点几分推送（按 daily_news_timezone 计时）
    daily_news_hour: int = 9
    daily_news_minute: int = 0
    daily_news_timezone: str = "Asia/Shanghai"
    # 两个榜单分别取前几条
    daily_news_weibo_count: int = 5
    daily_news_zhihu_count: int = 5

    # 调试日志开关
    ai_debug_log: bool = False
    
    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_key_prefix: str = "chat_ai:"
    
    # 联网搜索配置（博查 Bocha Web Search）
    web_search_enabled: bool = True
    web_search_api_key: str = ""
    web_search_count: int = 5
    web_search_max_length: int = 2000

    # RAGFlow 配置
    ragflow_enabled: bool = False
    ragflow_base_url: str = "http://127.0.0.1"
    ragflow_api_key: str = ""
    ragflow_kb_ids: list[str] = []
    ragflow_top_k: int = 5

    # 知识库聊天记录总结配置
    kb_summary_enabled: bool = True
    kb_summary_max_chars: int = 4000
    kb_summary_model: str = ""

    # TTS 语音朗读配置
    tts_enabled: bool = True
    tts_base_url: str = "http://qwen-tts:8000"
    tts_speaker: str = "Vivian"
    tts_language: str = "Chinese"
    tts_instruct: str = "用温柔可爱的语气，说标准普通话"
    tts_max_chars: int = 200
    
    # 系统提示词
    ai_system_prompt: str = (
        "You are MiMo, an AI assistant developed by Xiaomi. "
        "Today is date: Tuesday, December 16, 2025. "
        "Your knowledge cutoff date is December 2024."
    )

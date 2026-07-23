from pathlib import Path
from openai import AsyncOpenAI
from typing import Optional, Union
from nonebot import logger
import logging
import json
from datetime import datetime
from loguru import logger as loguru_logger

# AI专用日志配置
AI_LOG_FILE = Path(__file__).parent.parent.parent / "log" / "ai_log.log"
AI_REQUEST_LOG_FILE = Path(__file__).parent.parent.parent / "log" / "ai_request.log"
AI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# 创建AI专用的loguru logger（独立于主logger）
ai_logger = loguru_logger.opt(colors=False).bind(name="ai_service")
# 移除默认的stderr handler，只保留文件handler
ai_logger.remove()
ai_logger.add(
    AI_LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    encoding="utf-8",
)


class AIService:
    """AI 服务类"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        system_prompt: str,
        debug_log: bool = False,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.system_prompt = system_prompt
        self.debug_log = debug_log
        self.ai_logger = ai_logger.bind(model=model)

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    @staticmethod
    def load_prompt_from_file(file_path: Path) -> str:
        """从文件加载提示词"""
        try:
            if file_path.exists():
                return file_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass
        return ""

    async def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        发送聊天消息并获取回复

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词，如果为 None 则使用默认配置

        Returns:
            AI 回复内容
        """
        messages = [
            {
                "role": "system",
                "content": system_prompt or self.system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        # 记录请求内容
        request_log = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        self.ai_logger.info(json.dumps(request_log, ensure_ascii=False))

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        
        if response is None:
            raise ValueError("API 返回了 None 响应")
        
        if not response.choices:
            raise ValueError(f"API 返回空 choices: {response}")
        
        return response.choices[0].message.content

    async def chat_with_history(
        self,
        messages: list[dict[str, Union[str, list]]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        带历史记录的聊天

        Args:
            messages: 消息历史列表，格式为 [{"role": "user/assistant", "content": "..." 或 [...]}]
            system_prompt: 系统提示词

        Returns:
            AI 回复内容
        """
        full_messages = [
            {
                "role": "system",
                "content": system_prompt or self.system_prompt,
            },
        ] + messages

        # 记录请求内容
        request_log = {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        self.ai_logger.info(json.dumps(request_log, ensure_ascii=False))

        # 将请求内容写入专用文件
        self._save_request_to_file(full_messages)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        
        if response is None:
            raise ValueError("API 返回了 None 响应")
        
        if not response.choices:
            raise ValueError(f"API 返回空 choices: {response}")
        
        if response.choices[0] is None:
            raise ValueError(f"choices[0] 为 None: {response.choices}")
        
        return response.choices[0].message.content

    def _save_request_to_file(self, messages: list[dict[str, Union[str, list]]]):
        """将请求内容追加写入文件"""
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "model": self.model,
                "messages": messages,
            }
            with open(AI_REQUEST_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            self.ai_logger.warning(f"写入请求日志文件失败: {e}")

from pathlib import Path
from openai import AsyncOpenAI
from typing import Optional, Union
from nonebot import logger


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
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.system_prompt = system_prompt

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

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )

        # 调试信息
        logger.debug(f"API 响应类型: {type(response)}")
        logger.debug(f"API 响应内容: {response}")
        
        if response is None:
            raise ValueError("API 返回了 None 响应")
        
        if not response.choices:
            raise ValueError(f"API 返回空 choices: {response}")
        
        logger.debug(f"choices 类型: {type(response.choices)}")
        logger.debug(f"choices 内容: {response.choices}")
        
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

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )

        # 调试信息
        logger.debug(f"API 响应类型: {type(response)}")
        logger.debug(f"API 响应内容: {response}")
        
        if response is None:
            raise ValueError("API 返回了 None 响应")
        
        if not response.choices:
            raise ValueError(f"API 返回空 choices: {response}")
        
        logger.debug(f"choices 类型: {type(response.choices)}")
        logger.debug(f"choices 内容: {response.choices}")
        
        if response.choices[0] is None:
            raise ValueError(f"choices[0] 为 None: {response.choices}")
        
        logger.debug(f"message 类型: {type(response.choices[0].message)}")
        logger.debug(f"message 内容: {response.choices[0].message}")
        
        return response.choices[0].message.content

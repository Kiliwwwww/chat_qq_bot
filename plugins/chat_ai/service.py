from pathlib import Path
from openai import OpenAI
from typing import Optional


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

        self.client = OpenAI(
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

    def chat(
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

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )

        return response.choices[0].message.content

    def chat_with_history(
        self,
        messages: list[dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        带历史记录的聊天

        Args:
            messages: 消息历史列表，格式为 [{"role": "user/assistant", "content": "..."}]
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

        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )

        return response.choices[0].message.content

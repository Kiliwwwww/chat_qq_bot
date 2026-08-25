from pathlib import Path
from openai import AsyncOpenAI
from typing import Optional, Union
from nonebot import logger
import logging
import json
import re
import time
from datetime import datetime
from loguru import logger as loguru_logger
import httpx

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

# 知识库检索工具定义：由 AI 自主决定是否需要检索
RAG_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": (
            "在知识库中检索资料。知识库里包含群里的历史聊天记录（群友之前说过的话、讨论过的事）"
            "以及游戏规则文档。当群友的话涉及游戏玩法、历史事件、之前聊过的内容，"
            "或者你不确定群友在指什么、想更准确理解群友意思时，调用此工具检索相关资料。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用于检索的搜索关键词，尽量提炼出核心名词",
                }
            },
            "required": ["query"],
        },
    },
}


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

        httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,   # 连接超时 10s
                read=120.0,     # 读取超时 120s（大模型生成可能慢）
                write=10.0,     # 写入超时
                pool=10.0,      # 连接池超时
            ),
        )
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx_client,
            default_headers={"User-Agent": "curl/8.5.0"},
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
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        发送聊天消息并获取回复

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词，如果为 None 则使用默认配置
            model: 覆盖本次调用的模型，为 None 时使用实例默认模型
            max_tokens: 覆盖本次调用的最大 token 数
            temperature: 覆盖本次调用的采样温度

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

        request_start = time.time()
        self.ai_logger.info(f"开始调用 API (chat)，model={self.model}")
        try:
            response = await self.client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                top_p=self.top_p,
                timeout=120.0,
            )
        except Exception as e:
            elapsed = time.time() - request_start
            self.ai_logger.error(f"API 调用失败 (chat)，耗时 {elapsed:.2f}s: {e}")
            self._save_error_to_file(f"API 调用失败 (chat)，耗时 {elapsed:.2f}s: {e}")
            raise
        elapsed = time.time() - request_start
        self.ai_logger.info(f"API 调用成功 (chat)，耗时 {elapsed:.2f}s")
        self._save_error_to_file(f"API 调用成功 (chat)，耗时 {elapsed:.2f}s")
        
        if response is None:
            raise ValueError("API 返回了 None 响应")
        
        if not response.choices:
            raise ValueError(f"API 返回空 choices: {response}")
        
        return response.choices[0].message.content

    async def chat_with_history(
        self,
        messages: list[dict[str, Union[str, list]]],
        system_prompt: Optional[str] = None,
        rag_message: Optional[dict] = None,
    ) -> str:
        """
        带历史记录的聊天

        Args:
            messages: 消息历史列表，格式为 [{"role": "user/assistant", "content": "..." 或 [...]}]
            system_prompt: 系统提示词
            rag_message: 知识库 system message

        Returns:
            AI 回复内容
        """
        full_messages = [
            {
                "role": "system",
                "content": system_prompt or self.system_prompt,
            },
        ]
        
        # 知识库作为独立的 system message
        if rag_message:
            full_messages.append(rag_message)
        
        full_messages += messages

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

        request_start = time.time()
        self.ai_logger.info(f"开始调用 API，model={self.model}")
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                timeout=120.0,
            )
        except Exception as e:
            elapsed = time.time() - request_start
            self.ai_logger.error(f"API 调用失败，耗时 {elapsed:.2f}s: {e}")
            self._save_error_to_file(f"API 调用失败，耗时 {elapsed:.2f}s: {e}")
            raise
        elapsed = time.time() - request_start
        self.ai_logger.info(f"API 调用成功，耗时 {elapsed:.2f}s")
        self._save_error_to_file(f"API 调用成功，耗时 {elapsed:.2f}s")
        
        if response is None:
            raise ValueError("API 返回了 None 响应")
        
        if not response.choices:
            raise ValueError(f"API 返回空 choices: {response}")
        
        if response.choices[0] is None:
            raise ValueError(f"choices[0] 为 None: {response.choices}")
        
        return response.choices[0].message.content

    async def chat_with_rag(
        self,
        messages: list[dict[str, Union[str, list]]],
        system_prompt: Optional[str] = None,
        rag_client=None,
        max_tool_calls: int = 2,
    ) -> str:
        """
        带知识库检索工具的聊天：由 AI 自主决定是否需要检索知识库

        流程：
        1. 携带工具调用一次 API，让 AI 决定直接回答还是检索知识库
        2. 若 AI 决定检索（结构化 tool_calls 或文本形式 tool_call 均可），
           提取关键词检索知识库，把结果作为参考资料再让 AI 生成最终回复
        3. 若 AI 直接回答，或检索/工具调用失败，回退到普通对话

        Args:
            messages: 清理后的消息历史
            system_prompt: 系统提示词
            rag_client: RagFlow 客户端（用于检索知识库）
            max_tool_calls: 最多处理的检索关键词数量

        Returns:
            AI 回复内容
        """
        base_messages = [
            {
                "role": "system",
                "content": system_prompt or self.system_prompt,
            },
        ] + list(messages)

        request_start = time.time()
        self.ai_logger.info(f"开始调用 API (chat_with_rag)，model={self.model}")
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=base_messages,
                tools=[RAG_SEARCH_TOOL],
                tool_choice="auto",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                timeout=120.0,
            )
        except Exception as e:
            elapsed = time.time() - request_start
            self.ai_logger.warning(f"带工具调用失败，回退普通对话，耗时 {elapsed:.2f}s: {e}")
            return await self.chat_with_history(messages, system_prompt=system_prompt)

        first_msg = resp.choices[0].message
        content = first_msg.content or ""
        tool_calls = getattr(first_msg, "tool_calls", None) or []

        # 解析 AI 给出的检索关键词（兼容结构化 tool_calls 和文本形式 tool_call）
        queries: list[str] = []
        if tool_calls:
            for tc in tool_calls[:max_tool_calls]:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    query = str(args.get("query") or "").strip()
                except Exception:
                    query = ""
                if query:
                    queries.append(query)

        text_tool_call = "search_knowledge_base" in content

        # 若结构化未给出关键词，尝试从文本形式的 tool_call 中提取
        if not queries and text_tool_call:
            queries = self._extract_query_from_tool_call(content)

        # 不需要检索：直接返回 AI 的回复
        if not queries:
            if content.strip() and not text_tool_call:
                self.ai_logger.info("AI 决定直接回复，未检索知识库")
                return content
            self.ai_logger.warning("AI 返回空回复或仅有工具调用文本，回退普通对话")
            return await self.chat_with_history(messages, system_prompt=system_prompt)

        # AI 决定检索知识库
        self.ai_logger.info(f"AI 决定检索知识库: {queries}")
        rag_result = await rag_client.retrieve(queries[0])
        rag_message = rag_client.build_context_message(rag_result)

        return await self.chat_with_history(
            messages=messages,
            system_prompt=system_prompt,
            rag_message=rag_message,
        )

    @staticmethod
    def _extract_query_from_tool_call(text: str) -> list[str]:
        """
        从文本形式的工具调用中提取检索关键词。

        兼容常见格式，例如：
        <tool_call><function=search_knowledge_base><parameter=query>蛊修 元婴</parameter>...
        {"function": "search_knowledge_base", "query": "蛊修 元婴"}
        """
        queries: list[str] = []
        if not text:
            return queries

        # 格式1: <parameter=query>xxx</parameter>
        for m in re.finditer(r"<parameter=query[^>]*>(.*?)</parameter>", text, re.DOTALL):
            q = m.group(1).strip()
            if q and q not in queries:
                queries.append(q)

        # 格式2: JSON 文本 "query": "xxx"
        if not queries:
            for m in re.finditer(r"\"query\"\s*:\s*\"([^\"]+)\"", text):
                q = m.group(1).strip()
                if q and q not in queries:
                    queries.append(q)

        # 格式3: query 冒号/空格后直接跟关键词
        if not queries:
            for m in re.finditer(r"query[：:]\s*([^\n\"<>]+)", text):
                q = m.group(1).strip()
                if q and q not in queries:
                    queries.append(q)

        # 兜底：去掉 <tool_call> 标签等噪音后整句作为关键词
        if not queries:
            cleaned = re.sub(r"<[^>]+>", " ", text)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned and "search_knowledge_base" not in cleaned:
                queries.append(cleaned)

        return queries[:3]

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

    def _save_error_to_file(self, message: str):
        """将耗时/错误日志追加写入 ai_request.log"""
        try:
            timestamp = datetime.now().isoformat()
            with open(AI_REQUEST_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

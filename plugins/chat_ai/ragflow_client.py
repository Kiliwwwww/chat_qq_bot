from dataclasses import dataclass, field
from pathlib import Path

import httpx
from nonebot import logger


@dataclass
class RagChunk:
    """RAG 检索结果片段"""
    content: str
    document_name: str = ""
    chunk_id: str = ""
    similarity: float = 0.0


@dataclass
class RagResult:
    """RAG 检索结果"""
    chunks: list[RagChunk] = field(default_factory=list)
    raw_answer: str = ""


class RagFlowClient:
    """RAGFlow API 客户端"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        kb_ids: list[str],
        top_k: int = 5,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.kb_ids = kb_ids
        self.top_k = top_k
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def retrieve(self, question: str) -> RagResult:
        """
        从知识库检索相关内容

        Args:
            question: 用户问题

        Returns:
            RagResult 包含检索到的文本片段列表
        """
        if not self.kb_ids:
            logger.warning("RAGFlow 知识库 ID 为空，跳过检索")
            return RagResult()

        payload = {
            "question": question,
            "dataset_ids": self.kb_ids,
            "top_k": self.top_k,
        }

        try:
            resp = await self.client.post("/api/v1/retrieval", json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                logger.error(f"RAGFlow 检索失败: {data.get('message', '未知错误')}")
                return RagResult()

            chunks_data = data.get("data", {}).get("chunks", [])
            chunks = [
                RagChunk(
                    content=chunk.get("content", ""),
                    document_name=chunk.get("document_name", ""),
                    chunk_id=chunk.get("chunk_id", ""),
                    similarity=chunk.get("similarity", 0.0),
                )
                for chunk in chunks_data
                if chunk.get("content")
            ]

            return RagResult(chunks=chunks)

        except httpx.TimeoutException:
            logger.warning("RAGFlow 检索超时")
            return RagResult()
        except httpx.HTTPStatusError as e:
            logger.error(f"RAGFlow HTTP 错误: {e.response.status_code}")
            return RagResult()
        except Exception as e:
            logger.error(f"RAGFlow 检索异常: {e}")
            return RagResult()

    def build_context_prompt(self, result: RagResult, max_length: int = 2000) -> str:
        """
        将检索结果构建为可注入 system prompt 的上下文文本

        Args:
            result: RAG 检索结果
            max_length: 上下文最大字符数

        Returns:
            格式化的上下文字符串，无内容时返回空字符串
        """
        if not result.chunks:
            return ""

        parts: list[str] = []
        current_length = 0

        for i, chunk in enumerate(result.chunks, 1):
            text = chunk.content.strip()
            if not text:
                continue
            # 截断单个 chunk 避免过长
            if len(text) > 500:
                text = text[:500] + "..."
            entry = f"[{i}] {text}"
            if current_length + len(entry) > max_length:
                break
            parts.append(entry)
            current_length += len(entry)

        if not parts:
            return ""

        return (
            "\n\n## 参考知识库资料:\n"
            "以下是与用户问题相关的知识库内容，请结合这些资料回答用户问题。"
            "如果资料与问题无关，可以忽略。\n\n"
            + "\n\n".join(parts)
        )

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

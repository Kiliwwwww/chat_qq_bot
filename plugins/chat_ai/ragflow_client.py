import asyncio
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
                    document_name=chunk.get("document_keyword", ""),
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

    def build_context_message(self, result: RagResult, max_length: int = 2000) -> dict | None:
        """
        将检索结果构建为独立的 system message

        Args:
            result: RAG 检索结果
            max_length: 上下文最大字符数

        Returns:
            格式化的 system message dict，无内容时返回 None
        """
        if not result.chunks:
            return None

        parts: list[str] = []
        current_length = 0

        for i, chunk in enumerate(result.chunks, 1):
            text = chunk.content.strip()
            if not text:
                continue
            # if len(text) > 1000:
            #     text = text[:1000] + "..."
            
            doc_name = chunk.document_name.strip() if chunk.document_name else "未知文档"
            entry = f"[{i}]文件名称： {doc_name}\n{text}"
            
            if current_length + len(entry) > max_length:
                break
            parts.append(entry)
            current_length += len(entry)

        if not parts:
            return None

        content = (
            "## 参考知识库资料\n"
            "以下是与用户问题相关的知识库内容，请结合这些资料回答用户问题。"
            "如果资料与问题无关，可以忽略。\n\n"
            + "\n\n".join(parts)
        )

        return {"role": "system", "content": content}

    async def upload_document(self, dataset_id: str, file_path: Path, max_retries: int = 3) -> dict | None:
        """
        上传文档到指定知识库

        Args:
            dataset_id: 知识库ID
            file_path: 文件路径
            max_retries: 对 5xx 及连接类错误的最大重试次数

        Returns:
            API 响应数据，失败返回 None
        """
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        file_size = file_path.stat().st_size
        logger.info(f"开始上传文档: {file_path.name}, 大小: {file_size} bytes, 知识库: {dataset_id}")

        url = f"{self.base_url}/api/v1/datasets/{dataset_id}/documents"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(1, max_retries + 1):
            try:
                with open(file_path, "rb") as f:
                    files = {"file": (file_path.name, f, "text/plain")}
                    logger.info(f"请求URL: {url}")
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(url, files=files, headers=headers)

                logger.info(f"响应状态码: {resp.status_code}")

                if resp.status_code >= 500 and attempt < max_retries:
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"RAGFlow 上传文档服务端错误: status={resp.status_code}, body={resp.text[:500]}, "
                        f"{delay}s 后重试 ({attempt}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    logger.error(f"RAGFlow 上传文档失败: code={data.get('code')}, message={data.get('message')}")
                    return None

                logger.info(f"文档上传成功: {file_path.name} -> 知识库 {dataset_id}, 响应: {data}")
                return data.get("data")

            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempt < max_retries:
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"RAGFlow 上传文档请求异常: {type(e).__name__}: {e}, "
                        f"{delay}s 后重试 ({attempt}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"RAGFlow 上传文档请求异常: {type(e).__name__}: {e}")
                return None
            except httpx.HTTPStatusError as e:
                logger.error(f"RAGFlow 上传文档 HTTP 错误: status={e.response.status_code}, body={e.response.text[:500]}")
                return None
            except Exception as e:
                logger.error(f"RAGFlow 上传文档异常: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None

    async def parse_documents(self, dataset_id: str, document_ids: list[str], max_retries: int = 3) -> bool:
        """
        触发知识库文档解析

        Args:
            dataset_id: 知识库ID
            document_ids: 文档ID列表
            max_retries: 对 5xx 及连接类错误的最大重试次数

        Returns:
            是否成功
        """
        if not document_ids:
            logger.warning("文档ID列表为空，跳过解析")
            return False

        logger.info(f"开始触发文档解析: 知识库={dataset_id}, 文档ID={document_ids}")

        payload = {"document_ids": document_ids}

        for attempt in range(1, max_retries + 1):
            try:
                resp = await self.client.post(
                    f"/api/v1/datasets/{dataset_id}/chunks",
                    json=payload,
                )

                logger.info(f"解析响应状态码: {resp.status_code}")

                if resp.status_code >= 500 and attempt < max_retries:
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"RAGFlow 解析文档服务端错误: status={resp.status_code}, body={resp.text[:500]}, "
                        f"{delay}s 后重试 ({attempt}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    logger.error(f"RAGFlow 解析文档失败: code={data.get('code')}, message={data.get('message')}")
                    return False

                logger.info(f"文档解析已触发: 知识库 {dataset_id}, 文档数 {len(document_ids)}")
                return True

            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempt < max_retries:
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"RAGFlow 解析文档请求异常: {type(e).__name__}: {e}, "
                        f"{delay}s 后重试 ({attempt}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"RAGFlow 解析文档请求异常: {type(e).__name__}: {e}")
                return False
            except httpx.HTTPStatusError as e:
                logger.error(f"RAGFlow 解析文档 HTTP 错误: status={e.response.status_code}, body={e.response.text[:500]}")
                return False
            except Exception as e:
                logger.error(f"RAGFlow 解析文档异常: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False

    async def upload_and_parse(self, dataset_id: str, file_path: Path) -> bool:
        """
        上传文档并触发解析

        Args:
            dataset_id: 知识库ID
            file_path: 文件路径

        Returns:
            是否成功
        """
        result = await self.upload_document(dataset_id, file_path)
        if not result:
            return False

        doc_id = None
        if isinstance(result, dict):
            doc_id = result.get("id")
        elif isinstance(result, list) and result:
            doc_id = result[0].get("id")

        if not doc_id:
            logger.warning(f"上传成功但未获取到文档ID: {result}")
            return True

        return await self.parse_documents(dataset_id, [doc_id])

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

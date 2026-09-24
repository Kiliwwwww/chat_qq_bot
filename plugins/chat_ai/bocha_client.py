from dataclasses import dataclass, field

import httpx
from nonebot import logger


@dataclass
class WebSearchItem:
    """联网搜索结果条目"""
    title: str = ""
    url: str = ""
    snippet: str = ""
    summary: str = ""
    site_name: str = ""
    date_published: str = ""


@dataclass
class WebSearchResult:
    """联网搜索结果"""
    items: list[WebSearchItem] = field(default_factory=list)


class BochaWebSearchClient:
    """博查(Bocha) Web Search API 客户端"""

    BASE_URL = "https://api.bochaai.com"

    def __init__(
        self,
        api_key: str,
        count: int = 5,
        timeout: float = 15.0,
        db=None,
    ):
        self.api_key = api_key
        self.count = count
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self.db = db

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def search(self, query: str, count: int | None = None) -> WebSearchResult:
        """
        联网搜索

        Args:
            query: 搜索关键词
            count: 返回条数，为 None 时使用默认值

        Returns:
            WebSearchResult 包含搜索结果条目列表
        """
        if not query.strip():
            return WebSearchResult()

        payload = {
            "query": query,
            "summary": True,
            "count": count or self.count,
            "page": 1,
        }

        try:
            resp = await self.client.post("/v1/web-search", json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 200:
                logger.error(f"博查搜索失败: {data.get('msg', data)}")
                return WebSearchResult()

            pages = (data.get("data") or {}).get("webPages", {}).get("value", [])
            items = [
                WebSearchItem(
                    title=page.get("name", ""),
                    url=page.get("url", ""),
                    snippet=page.get("snippet", ""),
                    summary=page.get("summary", ""),
                    site_name=page.get("siteName", ""),
                    date_published=page.get("datePublished", ""),
                )
                for page in pages
            ]
            return WebSearchResult(items=items)

        except httpx.TimeoutException:
            logger.warning(f"博查搜索超时: {query}")
            return WebSearchResult()
        except httpx.HTTPStatusError as e:
            logger.error(f"博查搜索 HTTP 错误: {e.response.status_code} {e.response.text[:300]}")
            return WebSearchResult()
        except Exception as e:
            logger.error(f"博查搜索异常: {e}")
            return WebSearchResult()
        finally:
            if self.db:
                self.db.increment_stat("web_search_count")

    def build_context_message(self, result: WebSearchResult, max_length: int = 2000) -> dict | None:
        """
        将搜索结果构建为独立的 system message

        Args:
            result: 联网搜索结果
            max_length: 上下文最大字符数

        Returns:
            格式化的 system message dict，无内容时返回 None
        """
        if not result.items:
            return None

        parts: list[str] = []
        current_length = 0

        for i, item in enumerate(result.items, 1):
            text = (item.summary or item.snippet or "").strip()
            if not text:
                continue

            meta = " ".join(
                p for p in (item.site_name.strip(), item.date_published.strip()) if p
            )
            entry = f"[{i}] {item.title.strip()}\n"
            if meta:
                entry += f"来源: {meta}\n"
            entry += f"{text}\n链接: {item.url}"

            if current_length + len(entry) > max_length:
                break
            parts.append(entry)
            current_length += len(entry)

        if not parts:
            return None

        content = (
            "## 参考联网搜索结果\n"
            "以下是刚刚从互联网搜索到的实时资料，请结合这些资料回答用户问题，注意信息的时效性。"
            "如果资料与问题无关，可以忽略。\n\n"
            + "\n\n".join(parts)
        )

        return {"role": "system", "content": content}

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

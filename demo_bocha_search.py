"""博查联网搜索 Demo

用法:
    python demo_bocha_search.py 今天有什么科技新闻
"""

import json
import sys

import requests

API_KEY = "sk-a66c95e3fb9a4a1f915089ccbe5efafa"
URL = "https://api.bochaai.com/v1/web-search"


def web_search(query: str, count: int = 5) -> dict:
    resp = requests.post(
        URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={"query": query, "summary": True, "count": count, "page": 1},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    query = " ".join(sys.argv[1:]) or "今天有什么科技新闻"
    print(f"搜索: {query}\n")

    data = web_search(query)

    if data.get("code") != 200:
        print("请求失败:", json.dumps(data, ensure_ascii=False, indent=2))
        return

    pages = (data.get("data") or {}).get("webPages", {}).get("value", [])
    if not pages:
        print("无结果")
        return

    for i, page in enumerate(pages, 1):
        print(f"[{i}] {page.get('name', '')}")
        print(f"    链接: {page.get('url', '')}")
        print(f"    来源: {page.get('siteName', '')}  时间: {page.get('datePublished', '')}")
        summary = page.get("summary") or page.get("snippet") or ""
        print(f"    摘要: {summary}")
        print()

    print("--- 给模型看的上下文（summary 拼接）---")
    for page in pages:
        summary = page.get("summary") or page.get("snippet") or ""
        print(f"- {page.get('name', '')}: {summary} (来源: {page.get('url', '')})")


if __name__ == "__main__":
    main()

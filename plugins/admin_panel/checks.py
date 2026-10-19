from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import quote_plus

import httpx
from nonebot import get_plugin_config

BOCHA_BASE_URL = "https://api.bochaai.com"
CHECK_TIMEOUT = 15.0


def mask_key(value: str | None) -> str:
    if not value:
        return ""
    value = str(value)
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}****{value[-3:]}"


def _detail_from_response(response: httpx.Response) -> str:
    text = (response.text or "").strip().replace("\n", " ")
    if len(text) > 300:
        text = text[:300] + "..."
    return f"HTTP {response.status_code}: {text}" if text else f"HTTP {response.status_code}"


def _base(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": target["id"],
        "category": target["category"],
        "name": target["name"],
        "source": target.get("source", ""),
        "configured": bool(target.get("configured")),
        "in_use": bool(target.get("in_use")),
        "key_masked": mask_key(target.get("_api_key")),
        "base_url": target.get("base_url", ""),
        "model": target.get("model", ""),
    }


def _skip(target: dict[str, Any], reason: str) -> dict[str, Any]:
    result = _base(target)
    result.update(status="skipped", latency_ms=0, detail=reason, meta={})
    return result


def _ok(target: dict[str, Any], latency_ms: int, detail: str, meta: dict | None = None) -> dict[str, Any]:
    result = _base(target)
    result.update(status="ok", latency_ms=latency_ms, detail=detail, meta=meta or {})
    return result


def _fail(target: dict[str, Any], latency_ms: int, detail: str) -> dict[str, Any]:
    result = _base(target)
    result.update(status="fail", latency_ms=latency_ms, detail=detail, meta={})
    return result


async def _build_targets() -> list[dict[str, Any]]:
    from plugins.chat_ai.config import Config as ChatAIConfig
    from plugins.chat_ai.state import db

    config = get_plugin_config(ChatAIConfig)
    targets: list[dict[str, Any]] = []

    active = db.get_active_ai_service()
    active_id = active["id"] if active else None
    for row in db.get_all_ai_services():
        targets.append(
            {
                "id": f"ai-db-{row['id']}",
                "category": "ai",
                "name": row["name"],
                "source": "数据库",
                "configured": bool(row["api_key"]),
                "in_use": row["id"] == active_id,
                "_api_key": row["api_key"],
                "base_url": row["base_url"],
                "model": row["model"],
            }
        )

    targets.append(
        {
            "id": "ai-env",
            "category": "ai",
            "name": f".env 配置（{config.ai_model}）",
            "source": ".env",
            "configured": bool(config.ai_api_key),
            "in_use": active is None,
            "_api_key": config.ai_api_key,
            "base_url": config.ai_base_url,
            "model": config.ai_model,
        }
    )

    targets.append(
        {
            "id": "bocha",
            "category": "search",
            "name": "博查联网搜索",
            "source": ".env",
            "configured": bool(config.web_search_enabled and config.web_search_api_key),
            "in_use": bool(config.web_search_enabled),
            "_api_key": config.web_search_api_key,
            "base_url": BOCHA_BASE_URL,
            "model": "",
        }
    )

    targets.append(
        {
            "id": "ragflow",
            "category": "knowledge",
            "name": "RAGFlow 知识库",
            "source": ".env",
            "configured": bool(config.ragflow_enabled and config.ragflow_api_key),
            "in_use": bool(config.ragflow_enabled),
            "_api_key": config.ragflow_api_key,
            "base_url": config.ragflow_base_url,
            "model": "",
        }
    )

    targets.append(
        {
            "id": "tts",
            "category": "tts",
            "name": "Qwen3-TTS 语音服务",
            "source": ".env",
            "configured": bool(config.tts_enabled and config.tts_base_url),
            "in_use": bool(config.tts_enabled),
            "_api_key": "",
            "base_url": config.tts_base_url,
            "model": "",
        }
    )

    targets.append(
        {
            "id": "redis",
            "category": "redis",
            "name": "Redis",
            "source": "chat_ai 配置",
            "configured": bool(config.redis_host),
            "in_use": True,
            "_api_key": "",
            "base_url": f"{config.redis_host}:{config.redis_port}",
            "model": "",
        }
    )

    return targets


async def _test_ai(target: dict[str, Any]) -> dict[str, Any]:
    if not target.get("_api_key"):
        return _skip(target, "未配置 API Key")
    base_url = (target.get("base_url") or "").rstrip("/")
    model = target.get("model") or ""
    if not base_url:
        return _skip(target, "未配置 API 地址")

    headers = {
        "Authorization": f"Bearer {target['_api_key']}",
        "Content-Type": "application/json",
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(f"{base_url}/models", headers=headers)
            if response.status_code == 200:
                models: list[str] = []
                try:
                    payload = response.json()
                    for item in payload.get("data", []) or []:
                        if isinstance(item, dict) and item.get("id"):
                            models.append(str(item["id"]))
                except Exception:
                    models = []
                latency = int((time.perf_counter() - started) * 1000)
                detail = "模型列表接口可用"
                if model and models and model not in models:
                    detail += f"；未在列表中发现 {model}"
                return _ok(target, latency, detail, {"models": models[:50]})

            if response.status_code in (401, 403):
                latency = int((time.perf_counter() - started) * 1000)
                return _fail(target, latency, _detail_from_response(response))

            if response.status_code not in (400, 404, 405):
                latency = int((time.perf_counter() - started) * 1000)
                return _fail(target, latency, _detail_from_response(response))

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0,
            }
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            latency = int((time.perf_counter() - started) * 1000)
            if response.status_code == 200:
                return _ok(target, latency, "对话接口可用（最小请求）", {"models": []})
            return _fail(target, latency, _detail_from_response(response))
    except httpx.TimeoutException:
        latency = int((time.perf_counter() - started) * 1000)
        return _fail(target, latency, f"请求超时（{CHECK_TIMEOUT:.0f}s）")
    except Exception as exc:
        latency = int((time.perf_counter() - started) * 1000)
        return _fail(target, latency, f"{type(exc).__name__}: {exc}")


async def _test_bocha(target: dict[str, Any]) -> dict[str, Any]:
    if not target.get("_api_key"):
        return _skip(target, "未配置 API Key")
    started = time.perf_counter()
    headers = {
        "Authorization": f"Bearer {target['_api_key']}",
        "Content-Type": "application/json",
    }
    payload = {"query": "今天日期", "summary": False, "count": 1, "page": 1}
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT) as client:
            response = await client.post(
                f"{BOCHA_BASE_URL}/v1/web-search",
                headers=headers,
                json=payload,
            )
        latency = int((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            return _fail(target, latency, _detail_from_response(response))
        try:
            data = response.json()
        except Exception:
            return _fail(target, latency, "接口返回的不是 JSON")
        if data.get("code") != 200:
            return _fail(target, latency, f"code={data.get('code')} {data.get('msg', '')}")
        pages = (data.get("data") or {}).get("webPages", {}).get("value", [])
        return _ok(target, latency, f"搜索接口可用，返回 {len(pages)} 条", {"items": len(pages)})
    except httpx.TimeoutException:
        return _fail(target, int((time.perf_counter() - started) * 1000), "请求超时")
    except Exception as exc:
        return _fail(target, int((time.perf_counter() - started) * 1000), f"{type(exc).__name__}: {exc}")


async def _test_ragflow(target: dict[str, Any]) -> dict[str, Any]:
    if not target.get("_api_key"):
        return _skip(target, "未配置 API Key")
    base_url = (target.get("base_url") or "").rstrip("/")
    if not base_url:
        return _skip(target, "未配置服务地址")
    headers = {"Authorization": f"Bearer {target['_api_key']}"}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT) as client:
            response = await client.get(
                f"{base_url}/api/v1/datasets",
                headers=headers,
                params={"page": 1, "page_size": 30},
            )
        latency = int((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            return _fail(target, latency, _detail_from_response(response))
        try:
            data = response.json()
        except Exception:
            return _fail(target, latency, "接口返回的不是 JSON")
        if data.get("code") != 0:
            return _fail(target, latency, f"code={data.get('code')} {data.get('message', '')}")
        datasets = data.get("data") or []
        names = [str(item.get("name", "")) for item in datasets if isinstance(item, dict)]
        return _ok(
            target,
            latency,
            f"知识库接口可用，共 {len(datasets)} 个可见知识库",
            {"datasets": names[:30]},
        )
    except httpx.TimeoutException:
        return _fail(target, int((time.perf_counter() - started) * 1000), "请求超时")
    except Exception as exc:
        return _fail(target, int((time.perf_counter() - started) * 1000), f"{type(exc).__name__}: {exc}")


async def _test_tts(target: dict[str, Any]) -> dict[str, Any]:
    base_url = (target.get("base_url") or "").rstrip("/")
    if not base_url:
        return _skip(target, "未配置服务地址")
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT) as client:
            response = await client.get(f"{base_url}/health")
        latency = int((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            return _fail(target, latency, _detail_from_response(response))
        try:
            data = response.json()
        except Exception:
            return _ok(target, latency, "健康检查可用")
        loaded = bool(data.get("loaded"))
        detail = "服务在线" + ("，模型已加载" if loaded else "，模型尚未加载（首次合成时会加载）")
        return _ok(
            target,
            latency,
            detail,
            {
                "model": data.get("model", ""),
                "loaded": loaded,
                "device": data.get("device", ""),
                "speaker": data.get("default_speaker", ""),
            },
        )
    except httpx.TimeoutException:
        return _fail(target, int((time.perf_counter() - started) * 1000), "请求超时")
    except Exception as exc:
        return _fail(target, int((time.perf_counter() - started) * 1000), f"{type(exc).__name__}: {exc}")


def _redis_url(config: Any) -> str:
    password = quote_plus(config.redis_password) if config.redis_password else ""
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{config.redis_host}:{config.redis_port}/{config.redis_db}"


async def _test_redis(target: dict[str, Any]) -> dict[str, Any]:
    from plugins.chat_ai import state as chat_state
    from plugins.chat_ai.config import Config as ChatAIConfig

    config = get_plugin_config(ChatAIConfig)
    client = chat_state.redis_client
    should_close = False
    started = time.perf_counter()
    try:
        if client is None:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                _redis_url(config),
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=4,
                socket_timeout=4,
            )
            should_close = True
        pong = await asyncio.wait_for(client.ping(), timeout=5)
        latency = int((time.perf_counter() - started) * 1000)
        if pong:
            return _ok(target, latency, "PING 成功", {"host": config.redis_host, "db": config.redis_db})
        return _fail(target, latency, "PING 返回空结果")
    except asyncio.TimeoutError:
        return _fail(target, int((time.perf_counter() - started) * 1000), "连接超时")
    except Exception as exc:
        return _fail(target, int((time.perf_counter() - started) * 1000), f"{type(exc).__name__}: {exc}")
    finally:
        if should_close and client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


async def get_check_targets() -> list[dict[str, Any]]:
    targets = await _build_targets()
    return [_base(target) for target in targets]


async def run_checks(ids: list[str] | None = None) -> list[dict[str, Any]]:
    targets = await _build_targets()
    if ids:
        wanted = set(ids)
        targets = [item for item in targets if item["id"] in wanted]

    async def _run(target: dict[str, Any]) -> dict[str, Any]:
        if not target.get("configured"):
            reason = {
                "ai": "未配置 API Key",
                "search": "联网搜索未启用或未配置 API Key",
                "knowledge": "知识库未启用或未配置 API Key",
                "tts": "TTS 未启用或未配置地址",
                "redis": "未配置 Redis 地址",
            }.get(target["category"], "未配置")
            return _skip(target, reason)
        if target["category"] == "ai":
            return await _test_ai(target)
        if target["category"] == "search":
            return await _test_bocha(target)
        if target["category"] == "knowledge":
            return await _test_ragflow(target)
        if target["category"] == "tts":
            return await _test_tts(target)
        if target["category"] == "redis":
            return await _test_redis(target)
        return _skip(target, "未知检测类型")

    semaphore = asyncio.Semaphore(4)

    async def _guarded(target: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await _run(target)

    return await asyncio.gather(*(_guarded(item) for item in targets))

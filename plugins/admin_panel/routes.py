from __future__ import annotations

import asyncio
import hmac
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import nonebot
import psutil
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from nonebot import get_plugin_config
from pydantic import BaseModel, Field

from .actions import (
    ACTION_META,
    CHAT_LOG_DIR,
    LOG_DIR,
    create_backup,
    get_action_states,
    get_meme_stats,
    get_scheduler_jobs,
    list_files,
    read_tail_file,
    resolve_file,
    start_action,
)
from .auth import (
    COOKIE_NAME,
    check_csrf,
    create_session,
    get_config,
    is_authenticated,
    require_auth,
)
from .checks import get_check_targets, mask_key, run_checks
from .config import Config
from .log_stream import stream_log_file
from .runtime import STARTED_AT

STATIC_DIR = Path(__file__).resolve().parent / "static"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTH = [Depends(require_auth), Depends(check_csrf)]

router = APIRouter(prefix="/admin", tags=["admin-panel"])

_login_failures: dict[str, list[float]] = {}


class LoginPayload(BaseModel):
    password: str


class AIServiceCreate(BaseModel):
    name: str
    api_key: str
    base_url: str
    model: str


class AIServiceUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class UserPayload(BaseModel):
    user_id: int = Field(gt=0)


class GroupPayload(BaseModel):
    group_id: int = Field(gt=0)


class WelcomePayload(BaseModel):
    group_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=4000)


class AdKeywordPayload(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)


class KeywordPayload(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class KbGroupPayload(BaseModel):
    group_id: int = Field(gt=0)
    kb_id: str = Field(min_length=1, max_length=200)


class CheckPayload(BaseModel):
    ids: list[str] | None = None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune_failures(ip: str, window: float) -> list[float]:
    now = time.time()
    attempts = [item for item in _login_failures.get(ip, []) if now - item < window]
    _login_failures[ip] = attempts
    return attempts


def _chat_state():
    from plugins.chat_ai import state as chat_state

    return chat_state


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def index_page():
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/assets/{filename}", include_in_schema=False)
async def static_asset(filename: str):
    if filename not in {"app.js", "app.css"}:
        raise HTTPException(status_code=404, detail="文件不存在")
    media_type = "text/javascript" if filename.endswith(".js") else "text/css"
    return FileResponse(
        STATIC_DIR / filename,
        media_type=media_type,
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/api/session")
async def session_info(request: Request):
    config = get_config()
    return {
        "enabled": config.admin_panel_enabled,
        "password_configured": bool(config.admin_panel_password),
        "authenticated": is_authenticated(request),
    }


@router.post("/api/login")
async def login(request: Request, payload: LoginPayload):
    config = get_config()
    if not config.admin_panel_enabled:
        raise HTTPException(status_code=403, detail="管理面板未启用")
    if not config.admin_panel_password:
        raise HTTPException(
            status_code=503,
            detail="尚未配置 admin_panel_password，请在 .env 中设置后重启",
        )

    ip = _client_ip(request)
    window = max(1, config.admin_panel_login_window_seconds)
    attempts = _prune_failures(ip, window)
    if len(attempts) >= max(1, config.admin_panel_login_max_attempts):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")

    supplied = payload.password.encode("utf-8")
    expected = config.admin_panel_password.encode("utf-8")
    if not hmac.compare_digest(supplied, expected):
        attempts.append(time.time())
        _login_failures[ip] = attempts
        raise HTTPException(status_code=401, detail="密码错误")

    _login_failures.pop(ip, None)
    token = create_session(config.admin_panel_password, config.admin_panel_session_hours)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max(1, config.admin_panel_session_hours) * 3600,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/admin",
    )
    return response


@router.post("/api/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/admin")
    return response


@router.get("/api/overview", dependencies=AUTH)
async def overview():
    chat_state = _chat_state()
    db = chat_state.db
    bots = nonebot.get_bots()
    process = psutil.Process()
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage(str(PROJECT_ROOT))
    cpu_percent = await asyncio.to_thread(psutil.cpu_percent, 0.15)
    redis_result = (await run_checks(["redis"]))[0]

    active = db.get_active_ai_service()
    services = db.get_all_ai_services()
    stats = db.get_all_stats()
    jobs = get_scheduler_jobs()

    return {
        "timestamp": _iso_now(),
        "uptime_seconds": int(time.time() - STARTED_AT),
        "bots": [
            {
                "self_id": str(bot.self_id),
                "adapter": getattr(bot.adapter, "get_name", lambda: "")(),
            }
            for bot in bots.values()
        ],
        "system": {
            "cpu_percent": round(cpu_percent, 1),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total": memory.total,
                "used": memory.used,
                "percent": memory.percent,
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "percent": swap.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "percent": disk.percent,
            },
            "process": {
                "rss": process.memory_info().rss,
                "threads": process.num_threads(),
                "create_time": datetime.fromtimestamp(process.create_time())
                .astimezone()
                .isoformat(timespec="seconds"),
            },
        },
        "redis": redis_result,
        "stats": stats,
        "services": {
            "total": len(services),
            "active": (
                {
                    "id": active["id"],
                    "name": active["name"],
                    "model": active["model"],
                    "base_url": active["base_url"],
                    "key_masked": mask_key(active["api_key"]),
                }
                if active
                else None
            ),
        },
        "scheduler": {"job_count": len(jobs)},
        "counts": {
            "users": len(db.get_all_users()),
            "groups": len(db.get_all_groups()),
            "ad_keywords": len(db.get_all_ad_keywords()),
            "kb_groups": len(db.get_all_kb_groups()),
        },
    }


@router.get("/api/checks", dependencies=AUTH)
async def check_targets():
    return {"targets": await get_check_targets(), "checked_at": None, "results": []}


@router.post("/api/checks/run", dependencies=AUTH)
async def run_key_checks(payload: CheckPayload):
    results = await run_checks(payload.ids)
    return {"checked_at": _iso_now(), "results": results}


def _ai_service_public(service: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": service["id"],
        "name": service["name"],
        "base_url": service["base_url"],
        "model": service["model"],
        "is_active": bool(service.get("is_active")),
        "key_masked": mask_key(service.get("api_key")),
        "has_key": bool(service.get("api_key")),
    }


async def _ai_services_payload() -> dict[str, Any]:
    chat_state = _chat_state()
    services = chat_state.db.get_all_ai_services()
    return {
        "services": [_ai_service_public(item) for item in services],
        "active": next((item["id"] for item in services if item["is_active"]), None),
    }


@router.get("/api/ai-services", dependencies=AUTH)
async def list_ai_services():
    return await _ai_services_payload()


@router.post("/api/ai-services", dependencies=AUTH)
async def create_ai_service(payload: AIServiceCreate):
    name = payload.name.strip()
    api_key = payload.api_key.strip()
    base_url = payload.base_url.strip()
    model = payload.model.strip()
    if not all((name, api_key, base_url, model)):
        raise HTTPException(status_code=400, detail="名称、API Key、地址和模型都不能为空")
    chat_state = _chat_state()
    if not chat_state.db.add_ai_service(name, api_key, base_url, model):
        raise HTTPException(status_code=500, detail="添加失败，请查看日志")
    return await _ai_services_payload()


@router.put("/api/ai-services/{service_id}", dependencies=AUTH)
async def update_ai_service(service_id: int, payload: AIServiceUpdate):
    chat_state = _chat_state()
    existing = chat_state.db.get_ai_service(service_id)
    if not existing:
        raise HTTPException(status_code=404, detail="AI 服务不存在")

    name = (payload.name if payload.name is not None else existing["name"]).strip()
    base_url = (payload.base_url if payload.base_url is not None else existing["base_url"]).strip()
    model = (payload.model if payload.model is not None else existing["model"]).strip()
    api_key = (payload.api_key or "").strip() or existing["api_key"]
    if not all((name, api_key, base_url, model)):
        raise HTTPException(status_code=400, detail="名称、API Key、地址和模型都不能为空")

    if not chat_state.db.update_ai_service(service_id, name, api_key, base_url, model):
        raise HTTPException(status_code=500, detail="更新失败，请查看日志")
    if existing.get("is_active"):
        chat_state.init_ai_service()
    return await _ai_services_payload()


@router.delete("/api/ai-services/{service_id}", dependencies=AUTH)
async def delete_ai_service(service_id: int):
    chat_state = _chat_state()
    existing = chat_state.db.get_ai_service(service_id)
    if not existing:
        raise HTTPException(status_code=404, detail="AI 服务不存在")
    if existing.get("is_active"):
        raise HTTPException(status_code=400, detail="不能删除当前正在使用的服务，请先切换到其他服务")
    if not chat_state.db.remove_ai_service(service_id):
        raise HTTPException(status_code=500, detail="删除失败，请查看日志")
    return await _ai_services_payload()


@router.post("/api/ai-services/{service_id}/activate", dependencies=AUTH)
async def activate_ai_service(service_id: int):
    chat_state = _chat_state()
    existing = chat_state.db.get_ai_service(service_id)
    if not existing:
        raise HTTPException(status_code=404, detail="AI 服务不存在")
    if not chat_state.db.set_active_ai_service(service_id):
        raise HTTPException(status_code=500, detail="切换失败，请查看日志")
    chat_state.init_ai_service()
    return await _ai_services_payload()


async def _business_payload() -> dict[str, Any]:
    chat_state = _chat_state()
    db = chat_state.db
    return {
        "users": sorted(db.get_all_users()),
        "groups": sorted(db.get_all_groups()),
        "welcome": [
            {"group_id": group_id, "message": message}
            for group_id, message in sorted(db.get_all_welcome_messages().items())
        ],
        "ad_keywords": db.get_all_ad_keywords(),
        "ad_recall_groups": sorted(db.get_all_ad_recall_groups()),
        "kb_groups": [
            {"group_id": group_id, "kb_id": kb_id}
            for group_id, kb_id in sorted(db.get_all_kb_groups().items())
        ],
        "keywords": db.get_all_keywords(),
    }


@router.get("/api/business", dependencies=AUTH)
async def get_business():
    return await _business_payload()


@router.post("/api/whitelist/users", dependencies=AUTH)
async def add_whitelist_user(payload: UserPayload):
    chat_state = _chat_state()
    if not chat_state.db.add_user(payload.user_id):
        raise HTTPException(status_code=500, detail="添加失败")
    return await _business_payload()


@router.delete("/api/whitelist/users/{user_id}", dependencies=AUTH)
async def remove_whitelist_user(user_id: int):
    chat_state = _chat_state()
    if not chat_state.db.remove_user(user_id):
        raise HTTPException(status_code=500, detail="移除失败")
    return await _business_payload()


@router.post("/api/whitelist/groups", dependencies=AUTH)
async def add_whitelist_group(payload: GroupPayload):
    chat_state = _chat_state()
    if not chat_state.db.add_group(payload.group_id):
        raise HTTPException(status_code=500, detail="添加失败")
    return await _business_payload()


@router.delete("/api/whitelist/groups/{group_id}", dependencies=AUTH)
async def remove_whitelist_group(group_id: int):
    chat_state = _chat_state()
    if not chat_state.db.remove_group(group_id):
        raise HTTPException(status_code=500, detail="移除失败")
    return await _business_payload()


@router.put("/api/welcome", dependencies=AUTH)
async def set_welcome(payload: WelcomePayload):
    chat_state = _chat_state()
    if not chat_state.db.set_welcome_message(payload.group_id, payload.message):
        raise HTTPException(status_code=500, detail="保存失败")
    chat_state.group_welcome_messages[payload.group_id] = payload.message
    return await _business_payload()


@router.delete("/api/welcome/{group_id}", dependencies=AUTH)
async def remove_welcome(group_id: int):
    chat_state = _chat_state()
    if not chat_state.db.remove_welcome_message(group_id):
        raise HTTPException(status_code=500, detail="删除失败")
    chat_state.group_welcome_messages.pop(group_id, None)
    return await _business_payload()


@router.post("/api/ad-keywords", dependencies=AUTH)
async def add_ad_keyword(payload: AdKeywordPayload):
    chat_state = _chat_state()
    if not chat_state.db.add_ad_keyword(payload.keyword.strip()):
        raise HTTPException(status_code=500, detail="添加失败")
    return await _business_payload()


@router.delete("/api/ad-keywords/{keyword_id}", dependencies=AUTH)
async def remove_ad_keyword(keyword_id: int):
    chat_state = _chat_state()
    if not chat_state.db.remove_ad_keyword(keyword_id):
        raise HTTPException(status_code=500, detail="删除失败")
    return await _business_payload()


@router.post("/api/ad-recall-groups", dependencies=AUTH)
async def add_ad_recall_group(payload: GroupPayload):
    chat_state = _chat_state()
    if not chat_state.db.add_ad_recall_group(payload.group_id):
        raise HTTPException(status_code=500, detail="添加失败")
    chat_state.ad_recall_groups.add(payload.group_id)
    return await _business_payload()


@router.delete("/api/ad-recall-groups/{group_id}", dependencies=AUTH)
async def remove_ad_recall_group(group_id: int):
    chat_state = _chat_state()
    if not chat_state.db.remove_ad_recall_group(group_id):
        raise HTTPException(status_code=500, detail="移除失败")
    chat_state.ad_recall_groups.discard(group_id)
    return await _business_payload()


@router.put("/api/kb-groups", dependencies=AUTH)
async def set_kb_group(payload: KbGroupPayload):
    chat_state = _chat_state()
    if not chat_state.db.add_kb_group(payload.group_id, payload.kb_id.strip()):
        raise HTTPException(status_code=500, detail="保存失败")
    chat_state.kb_groups[payload.group_id] = payload.kb_id.strip()
    return await _business_payload()


@router.delete("/api/kb-groups/{group_id}", dependencies=AUTH)
async def remove_kb_group(group_id: int):
    chat_state = _chat_state()
    if not chat_state.db.remove_kb_group(group_id):
        raise HTTPException(status_code=500, detail="移除失败")
    chat_state.kb_groups.pop(group_id, None)
    return await _business_payload()


@router.post("/api/keywords", dependencies=AUTH)
async def add_keyword(payload: KeywordPayload):
    chat_state = _chat_state()
    if not chat_state.db.add_keyword(payload.content.strip()):
        raise HTTPException(status_code=500, detail="添加失败")
    return await _business_payload()


@router.delete("/api/keywords/{keyword_id}", dependencies=AUTH)
async def remove_keyword(keyword_id: int):
    chat_state = _chat_state()
    if not chat_state.db.remove_keyword(keyword_id):
        raise HTTPException(status_code=500, detail="删除失败")
    return await _business_payload()


@router.get("/api/logs/files", dependencies=AUTH)
async def log_files():
    return {"files": list_files(LOG_DIR, {".log"}, limit=500)}


@router.get("/api/logs/file/{name}", dependencies=AUTH)
async def log_file(
    name: str,
    lines: int = 200,
    keyword: str = "",
    level: str = "",
    full: bool = False,
):
    try:
        return await asyncio.to_thread(
            read_tail_file,
            LOG_DIR,
            name,
            lines,
            keyword,
            level,
            full,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/logs/stream/{name}", dependencies=AUTH)
async def log_stream(request: Request, name: str, initial_lines: int = 100):
    try:
        path = resolve_file(LOG_DIR, name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await stream_log_file(request, path, initial_lines)


@router.get("/api/chatlogs/files", dependencies=AUTH)
async def chat_log_files():
    return {"files": list_files(CHAT_LOG_DIR, {".txt"}, limit=1000)}


@router.get("/api/chatlogs/file/{name}", dependencies=AUTH)
async def chat_log_file(
    name: str,
    lines: int = 200,
    keyword: str = "",
    level: str = "",
    full: bool = False,
):
    try:
        return await asyncio.to_thread(
            read_tail_file,
            CHAT_LOG_DIR,
            name,
            lines,
            keyword,
            level,
            full,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/chatlogs/stream/{name}", dependencies=AUTH)
async def chat_log_stream(request: Request, name: str, initial_lines: int = 100):
    try:
        path = resolve_file(CHAT_LOG_DIR, name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await stream_log_file(request, path, initial_lines)


@router.get("/api/actions", dependencies=AUTH)
async def actions():
    return {
        "scheduler": get_scheduler_jobs(),
        "actions": get_action_states(),
        "meta": ACTION_META,
    }


@router.post("/api/actions/{name}", dependencies=AUTH)
async def trigger_action(name: str):
    try:
        return await start_action(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/memes", dependencies=AUTH)
async def meme_stats():
    return await asyncio.to_thread(get_meme_stats)


@router.get("/api/backup", dependencies=AUTH)
async def backup_database():
    data = await create_backup()
    filename = f"qqbot-backup-{datetime.now():%Y%m%d-%H%M%S}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/config", dependencies=AUTH)
async def config_summary():
    from plugins.chat_ai.config import Config as ChatAIConfig

    chat_config = get_plugin_config(ChatAIConfig)
    panel_config = get_plugin_config(Config)
    sections = [
        {
            "title": "AI 对话（.env 默认配置）",
            "items": [
                {"label": "API 地址", "value": chat_config.ai_base_url},
                {"label": "模型", "value": chat_config.ai_model},
                {"label": "API Key", "value": mask_key(chat_config.ai_api_key) or "未配置", "secret": True},
                {"label": "最大生成", "value": str(chat_config.ai_max_tokens)},
                {"label": "温度", "value": str(chat_config.ai_temperature)},
                {"label": "上下文条数", "value": str(chat_config.ai_context_limit)},
                {"label": "调试日志", "value": "开启" if chat_config.ai_debug_log else "关闭"},
            ],
        },
        {
            "title": "联网搜索",
            "items": [
                {"label": "启用", "value": "是" if chat_config.web_search_enabled else "否"},
                {"label": "API Key", "value": mask_key(chat_config.web_search_api_key) or "未配置", "secret": True},
                {"label": "结果条数", "value": str(chat_config.web_search_count)},
            ],
        },
        {
            "title": "RAGFlow 知识库",
            "items": [
                {"label": "启用", "value": "是" if chat_config.ragflow_enabled else "否"},
                {"label": "服务地址", "value": chat_config.ragflow_base_url},
                {"label": "API Key", "value": mask_key(chat_config.ragflow_api_key) or "未配置", "secret": True},
                {"label": "知识库 ID", "value": ", ".join(chat_config.ragflow_kb_ids) or "未配置"},
                {"label": "召回条数", "value": str(chat_config.ragflow_top_k)},
            ],
        },
        {
            "title": "语音服务",
            "items": [
                {"label": "启用", "value": "是" if chat_config.tts_enabled else "否"},
                {"label": "服务地址", "value": chat_config.tts_base_url},
                {"label": "音色", "value": chat_config.tts_speaker},
                {"label": "语言", "value": chat_config.tts_language},
                {"label": "最大字数", "value": str(chat_config.tts_max_chars)},
            ],
        },
        {
            "title": "Redis",
            "items": [
                {"label": "地址", "value": f"{chat_config.redis_host}:{chat_config.redis_port}"},
                {"label": "数据库", "value": str(chat_config.redis_db)},
                {
                    "label": "密码",
                    "value": mask_key(chat_config.redis_password) or "未设置",
                    "secret": True,
                },
            ],
        },
        {
            "title": "管理面板",
            "items": [
                {"label": "启用", "value": "是" if panel_config.admin_panel_enabled else "否"},
                {
                    "label": "登录密码",
                    "value": "已配置" if panel_config.admin_panel_password else "未配置",
                    "secret": True,
                },
                {"label": "会话有效期", "value": f"{panel_config.admin_panel_session_hours} 小时"},
            ],
        },
    ]
    return {"sections": sections, "readonly": True}

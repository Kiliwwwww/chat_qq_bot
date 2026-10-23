from __future__ import annotations

import asyncio
import hmac
import json
import mimetypes
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

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
from .reports import get_ai_usage, get_group_activity, get_operations
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


class GroupSendPayload(BaseModel):
    group_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=4000)


class AdKeywordPayload(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)


class KeywordPayload(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class KbGroupPayload(BaseModel):
    group_id: int = Field(gt=0)
    kb_id: str = Field(min_length=1, max_length=200)


class GroupPromptPayload(BaseModel):
    group_id: int = Field(gt=0)
    name: str = Field(default="", max_length=100)
    prompt: str = Field(min_length=1, max_length=100000)


class CheckPayload(BaseModel):
    ids: list[str] | None = None


class SkillPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    type: Literal["prompt", "tool"]
    content: str = Field(min_length=1, max_length=50000)
    scope: Literal["global", "group"] = "global"
    group_id: int | None = None
    enabled: bool = True


class SkillEnabledPayload(BaseModel):
    enabled: bool


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


async def _wait_for_bots(timeout: float = 5.0) -> list[Any]:
    """等待 Bot 上线，返回当前已连接的所有 Bot。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, timeout)
    while True:
        bots = list(nonebot.get_bots().values())
        if bots or loop.time() >= deadline:
            return bots
        await asyncio.sleep(0.5)


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _serve_index() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def index_page():
    return _serve_index()


PAGE_PATHS = (
    "overview",
    "reports",
    "checks",
    "ai",
    "services",
    "skills",
    "business",
    "prompts",
    "commands",
    "logs",
    "tasks",
    "config",
)


for _page in PAGE_PATHS:
    router.add_api_route(
        f"/{_page}",
        _serve_index,
        methods=["GET"],
        include_in_schema=False,
        name=f"admin_page_{_page}",
    )


@router.get("/assets/{asset_path:path}", include_in_schema=False)
async def static_asset(asset_path: str):
    base = STATIC_DIR.resolve()
    target = (STATIC_DIR / asset_path).resolve()
    try:
        rel = target.relative_to(base).as_posix()
    except ValueError:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not (rel.startswith("vendor/") or rel.startswith("js/") or rel.startswith("css/")):
        raise HTTPException(status_code=404, detail="文件不存在")
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    cacheable = rel.startswith("vendor/")
    return FileResponse(
        target,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=604800" if cacheable else "no-cache"
        },
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


@router.get("/api/commands", dependencies=AUTH)
async def list_commands():
    from .command_catalog import COMMAND_GROUPS, COMMAND_NOTES

    total = sum(len(group["commands"]) for group in COMMAND_GROUPS)
    return {
        "groups": COMMAND_GROUPS,
        "notes": COMMAND_NOTES,
        "total": total,
    }


@router.get("/api/reports/group-activity", dependencies=AUTH)
async def report_group_activity(days: int = 7, group_id: str = "all"):
    return await asyncio.to_thread(get_group_activity, days, group_id)


@router.get("/api/reports/ai-usage", dependencies=AUTH)
async def report_ai_usage(days: int = 7):
    return await asyncio.to_thread(get_ai_usage, days)


@router.get("/api/reports/operations", dependencies=AUTH)
async def report_operations(days: int = 7):
    return await asyncio.to_thread(get_operations, days)


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


def _normalize_skill_payload(payload: SkillPayload) -> dict[str, Any]:
    from plugins.chat_ai.skills import RESERVED_TOOL_NAMES, parse_tool_config

    name = payload.name.strip()
    title = payload.title.strip()
    description = payload.description.strip()
    content = payload.content.strip()
    if not name or not title or not content:
        raise HTTPException(status_code=400, detail="标识、名称和内容都不能为空")
    if name in RESERVED_TOOL_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"标识 {name} 是内置工具名，请换一个",
        )

    group_id = payload.group_id
    if payload.scope == "group":
        if not group_id or group_id <= 0:
            raise HTTPException(status_code=400, detail="作用域为指定群时必须填写群号")
    else:
        group_id = None

    if payload.type == "tool":
        try:
            config = parse_tool_config(content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        content = json.dumps(config, ensure_ascii=False, indent=2)

    return {
        "name": name,
        "title": title,
        "description": description,
        "type": payload.type,
        "content": content,
        "scope": payload.scope,
        "group_id": group_id,
        "enabled": payload.enabled,
    }


def _skill_public(skill: dict[str, Any]) -> dict[str, Any]:
    item = {
        "id": skill["id"],
        "name": skill["name"],
        "title": skill["title"],
        "description": skill.get("description") or "",
        "type": skill["type"],
        "content": skill.get("content") or "",
        "scope": skill.get("scope") or "global",
        "group_id": skill.get("group_id"),
        "enabled": bool(skill.get("enabled")),
        "created_at": skill.get("created_at"),
        "updated_at": skill.get("updated_at"),
    }
    if item["type"] == "tool":
        try:
            item["config"] = json.loads(item["content"])
        except (TypeError, ValueError):
            item["config"] = None
    return item


@router.get("/api/skills", dependencies=AUTH)
async def list_skills():
    from plugins.chat_ai.skills import RESERVED_TOOL_NAMES

    chat_state = _chat_state()
    skills = chat_state.db.get_all_skills()
    return {
        "skills": [_skill_public(skill) for skill in skills],
        "reserved_names": sorted(RESERVED_TOOL_NAMES),
    }


@router.post("/api/skills", dependencies=AUTH)
async def create_skill(payload: SkillPayload):
    data = _normalize_skill_payload(payload)
    chat_state = _chat_state()
    if chat_state.db.get_skill_by_name(data["name"]):
        raise HTTPException(status_code=409, detail="技能标识已存在，请换一个")
    if not chat_state.db.add_skill(
        data["name"],
        data["title"],
        data["description"],
        data["type"],
        data["content"],
        data["scope"],
        data["group_id"],
        data["enabled"],
    ):
        raise HTTPException(status_code=500, detail="新增失败，请查看日志")
    return await list_skills()


@router.put("/api/skills/{skill_id}", dependencies=AUTH)
async def update_skill(skill_id: int, payload: SkillPayload):
    data = _normalize_skill_payload(payload)
    chat_state = _chat_state()
    if not chat_state.db.get_skill(skill_id):
        raise HTTPException(status_code=404, detail="技能不存在")
    same_name = chat_state.db.get_skill_by_name(data["name"])
    if same_name and same_name["id"] != skill_id:
        raise HTTPException(status_code=409, detail="技能标识已存在，请换一个")
    if not chat_state.db.update_skill(
        skill_id,
        data["name"],
        data["title"],
        data["description"],
        data["type"],
        data["content"],
        data["scope"],
        data["group_id"],
        data["enabled"],
    ):
        raise HTTPException(status_code=500, detail="更新失败，请查看日志")
    return await list_skills()


@router.patch("/api/skills/{skill_id}/enabled", dependencies=AUTH)
async def toggle_skill(skill_id: int, payload: SkillEnabledPayload):
    chat_state = _chat_state()
    if not chat_state.db.get_skill(skill_id):
        raise HTTPException(status_code=404, detail="技能不存在")
    if not chat_state.db.set_skill_enabled(skill_id, payload.enabled):
        raise HTTPException(status_code=500, detail="更新失败，请查看日志")
    return await list_skills()


@router.delete("/api/skills/{skill_id}", dependencies=AUTH)
async def delete_skill(skill_id: int):
    chat_state = _chat_state()
    if not chat_state.db.get_skill(skill_id):
        raise HTTPException(status_code=404, detail="技能不存在")
    if not chat_state.db.remove_skill(skill_id):
        raise HTTPException(status_code=500, detail="删除失败，请查看日志")
    return await list_skills()


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


def _group_prompt_public(item: dict[str, Any]) -> dict[str, Any]:
    prompt = item.get("prompt") or ""
    return {
        "group_id": item["group_id"],
        "name": item.get("name") or "",
        "prompt": prompt,
        "length": len(prompt),
        "summary": prompt[:80].replace("\n", " "),
        "updated_at": item.get("updated_at"),
    }


@router.get("/api/group-prompts", dependencies=AUTH)
async def list_group_prompts():
    chat_state = _chat_state()
    db = chat_state.db
    items = db.get_all_group_prompts()
    whitelisted = set(db.get_all_groups())
    return {
        "items": [_group_prompt_public(item) for item in items],
        "whitelisted_groups": sorted(whitelisted),
    }


@router.get("/api/group-prompts/default-preview", dependencies=AUTH)
async def group_prompt_default_preview():
    chat_state = _chat_state()
    from plugins.chat_ai.config import Config as ChatAIConfig
    from plugins.chat_ai.service import AIService

    prompt_file = (
        chat_state.PROMPT_KIND_FILE
        if chat_state.current_prompt_mode == "kind"
        else chat_state.PROMPT_FILE
    )
    prompt = AIService.load_prompt_from_file(prompt_file)
    chat_config = get_plugin_config(ChatAIConfig)
    if not prompt:
        prompt = chat_config.ai_system_prompt
    if prompt:
        prompt = prompt.replace("{admin_qq}", str(chat_config.admin_qq))
        prompt = prompt.replace("{admin_name}", chat_config.admin_name)
    return {
        "mode": chat_state.current_prompt_mode,
        "prompt": prompt,
    }


@router.post("/api/group-prompts", dependencies=AUTH)
async def create_group_prompt(payload: GroupPromptPayload):
    chat_state = _chat_state()
    if chat_state.db.get_group_prompt(payload.group_id):
        raise HTTPException(status_code=409, detail="该群已配置专属提示词，请使用编辑")
    if not chat_state.db.set_group_prompt(
        payload.group_id, payload.prompt, payload.name.strip()
    ):
        raise HTTPException(status_code=500, detail="保存失败，请查看日志")
    return await list_group_prompts()


@router.put("/api/group-prompts/{group_id}", dependencies=AUTH)
async def update_group_prompt(group_id: int, payload: GroupPromptPayload):
    chat_state = _chat_state()
    if payload.group_id != group_id:
        raise HTTPException(status_code=400, detail="群号不匹配")
    if not chat_state.db.get_group_prompt(group_id):
        raise HTTPException(status_code=404, detail="该群尚未配置专属提示词")
    if not chat_state.db.set_group_prompt(
        group_id, payload.prompt, payload.name.strip()
    ):
        raise HTTPException(status_code=500, detail="保存失败，请查看日志")
    return await list_group_prompts()


@router.delete("/api/group-prompts/{group_id}", dependencies=AUTH)
async def delete_group_prompt(group_id: int):
    chat_state = _chat_state()
    if not chat_state.db.get_group_prompt(group_id):
        raise HTTPException(status_code=404, detail="该群尚未配置专属提示词")
    if not chat_state.db.delete_group_prompt(group_id):
        raise HTTPException(status_code=500, detail="删除失败，请查看日志")
    return await list_group_prompts()


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


@router.get("/api/groups", dependencies=AUTH)
async def list_bot_groups():
    chat_db = _chat_state().db
    whitelisted = {int(group_id) for group_id in chat_db.get_all_groups()}
    groups: dict[int, str] = {}
    error = ""
    bots = await _wait_for_bots(3.0)
    if bots:
        for bot in bots:
            try:
                for item in await bot.get_group_list():
                    group_id = int(item.get("group_id") or 0)
                    if group_id:
                        groups[group_id] = str(item.get("group_name") or "").strip()
            except Exception as exc:
                error = str(exc)
                nonebot.logger.warning(f"获取群列表失败: {exc}")

        # 部分 OneBot 实现不会在群列表里返回群名，单独补一次群信息
        for group_id in whitelisted:
            if groups.get(group_id):
                continue
            for bot in bots:
                try:
                    info = await bot.get_group_info(group_id=group_id)
                    name = str(info.get("group_name") or "").strip()
                except Exception:
                    continue
                if name:
                    groups[group_id] = name
                    break

        chat_db.save_group_names({gid: name for gid, name in groups.items() if name})

    # 机器人离线时回退到数据库里缓存的群名，避免下拉框只剩群号
    for group_id, name in chat_db.get_all_group_names().items():
        groups.setdefault(int(group_id), name)
    for group_id in whitelisted:
        groups.setdefault(group_id, "")

    return {
        "groups": [
            {"group_id": group_id, "group_name": name}
            for group_id, name in sorted(groups.items())
        ],
        "bot_online": bool(bots),
        "error": error,
    }


@router.post("/api/send-group", dependencies=AUTH)
async def send_group_message(payload: GroupSendPayload):
    bots = await _wait_for_bots(5.0)
    if not bots:
        raise HTTPException(status_code=503, detail="机器人不在线，无法发送消息")
    content = payload.message.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    last_error: Exception | None = None
    for bot in bots:
        try:
            await bot.send_group_msg(group_id=payload.group_id, message=content)
            nonebot.logger.info(f"管理面板向群 {payload.group_id} 发送消息: {content[:30]}")
            return {"ok": True, "group_id": payload.group_id}
        except Exception as error:
            last_error = error
            nonebot.logger.warning(f"向群 {payload.group_id} 发送消息失败: {error}")
    raise HTTPException(status_code=400, detail=f"发送失败: {last_error}")


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

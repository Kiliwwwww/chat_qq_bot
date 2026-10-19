from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from nonebot import get_plugin_config

from .config import Config

COOKIE_NAME = "qqbot_admin_session"
_AUTH_SALT = b"qqbot-admin-panel:v1"


def get_config() -> Config:
    return get_plugin_config(Config)


def _secret(password: str) -> bytes:
    return hashlib.sha256(_AUTH_SALT + password.encode("utf-8")).digest()


def create_session(password: str, hours: int) -> str:
    expires_at = int(time.time() + max(1, hours) * 3600)
    payload = str(expires_at)
    signature = hmac.new(_secret(password), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_session(token: str | None, password: str) -> bool:
    if not token or not password:
        return False
    try:
        expires_text, signature = token.split(".", 1)
        expires_at = int(expires_text)
    except (ValueError, TypeError):
        return False
    if expires_at < int(time.time()):
        return False
    expected = hmac.new(
        _secret(password),
        expires_text.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def is_authenticated(request: Request) -> bool:
    config = get_config()
    if not config.admin_panel_enabled or not config.admin_panel_password:
        return False
    return verify_session(
        request.cookies.get(COOKIE_NAME),
        config.admin_panel_password,
    )


def require_auth(request: Request) -> None:
    config = get_config()
    if not config.admin_panel_enabled:
        raise HTTPException(status_code=404, detail="管理面板未启用")
    if not config.admin_panel_password:
        raise HTTPException(
            status_code=503,
            detail="尚未配置 admin_panel_password，请在 .env 中设置后重启",
        )
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="请先登录")


def check_csrf(request: Request) -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if request.headers.get("x-admin-request") != "1":
        raise HTTPException(status_code=403, detail="非法请求")
    origin = request.headers.get("origin")
    if not origin:
        return
    parsed = urlparse(origin)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    host = host.split(",")[0].strip()
    if parsed.netloc and host and parsed.netloc != host:
        raise HTTPException(status_code=403, detail="跨站请求被拒绝")

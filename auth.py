"""momoqun 控制面鉴权（API + Agent WebSocket）。

- ``security.api_token`` 非空（或环境变量 ``MOMOQUN_API_TOKEN``）时启用鉴权
- 空 token：鉴权关闭（仅打日志警告），便于本地开发迁移
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Dict, Optional

from fastapi import Request

logger = logging.getLogger("auth")

_API_TOKEN: Optional[str] = None
_ALLOW_SHELL_EXEC: bool = False
_HEARTBEAT_TIMEOUT_SEC: float = 30.0


def load_security_config(settings: Optional[dict] = None) -> None:
    """从 settings['security'] 与环境变量加载鉴权配置。"""
    global _API_TOKEN, _ALLOW_SHELL_EXEC, _HEARTBEAT_TIMEOUT_SEC
    sec: Dict[str, Any] = {}
    if isinstance(settings, dict):
        raw = settings.get("security")
        if isinstance(raw, dict):
            sec = raw

    token = (os.environ.get("MOMOQUN_API_TOKEN") or sec.get("api_token") or "").strip()
    _API_TOKEN = token or None
    _ALLOW_SHELL_EXEC = bool(sec.get("allow_shell_exec", False))
    try:
        _HEARTBEAT_TIMEOUT_SEC = max(5.0, float(sec.get("heartbeat_timeout_sec", 30)))
    except (TypeError, ValueError):
        _HEARTBEAT_TIMEOUT_SEC = 30.0

    if _API_TOKEN:
        logger.info(
            "鉴权已启用 (shell_exec=%s, heartbeat_timeout=%.0fs)",
            _ALLOW_SHELL_EXEC,
            _HEARTBEAT_TIMEOUT_SEC,
        )
    else:
        logger.warning(
            "鉴权未启用：请在 config/settings.yaml 的 security.api_token 设置令牌，"
            "或设置环境变量 MOMOQUN_API_TOKEN"
        )
    if _ALLOW_SHELL_EXEC:
        logger.warning("security.allow_shell_exec=true：Agent 可通过 shell_exec 执行 adb shell")


def auth_enabled() -> bool:
    return _API_TOKEN is not None


def allow_shell_exec() -> bool:
    return _ALLOW_SHELL_EXEC


def heartbeat_timeout_sec() -> float:
    return _HEARTBEAT_TIMEOUT_SEC


def get_api_token() -> Optional[str]:
    """返回当前配置的 token（仅供已鉴权接口下发给本机 UI）。"""
    return _API_TOKEN


def verify_token(token: Optional[str]) -> bool:
    if not auth_enabled():
        return True
    if not token:
        return False
    assert _API_TOKEN is not None
    return secrets.compare_digest(token, _API_TOKEN)


def get_token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    hdr = request.headers.get("X-Momoqun-Token")
    if hdr:
        return hdr.strip()
    q = request.query_params.get("token")
    return q.strip() if q else None


def auth_status_payload() -> dict:
    return {
        "auth_required": auth_enabled(),
        "shell_exec_allowed": allow_shell_exec(),
        "heartbeat_timeout_sec": heartbeat_timeout_sec(),
    }

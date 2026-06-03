"""momoqun 服务器：FastAPI + Web UI + 内置设备管理

用法:
    python server.py --port 5100
"""

from __future__ import annotations

import asyncio
import atexit
import collections
import ipaddress
import logging
import os
import signal
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import uvicorn
import yaml
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from auth import (
    auth_enabled,
    auth_status_payload,
    get_api_token,
    get_token_from_request,
    load_security_config,
    verify_token,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE, "config", "settings.yaml")
ELEMENTS_PATH = os.path.join(BASE, "config", "elements.yaml")

# 实际监听端口。由入口（app.py / server.main）写入，前端 /api/master-address 据此拼 ws_url。
MASTER_PORT = 5100

# ---------------------------------------------------------------------------
# FastAPI app（lifespan：鉴权配置 + Agent 心跳看门狗）
# ---------------------------------------------------------------------------
logger = logging.getLogger("server")
_agent_watchdog_task: Any = None


@asynccontextmanager
async def _app_lifespan(application: FastAPI):
    global _agent_watchdog_task
    try:
        load_security_config(_load_settings())
    except Exception:
        logger.exception("加载鉴权配置失败")
    try:
        from agent_router import get_router, _heartbeat_watchdog

        router = get_router()
        router.bind_loop(asyncio.get_running_loop())
        _agent_watchdog_task = asyncio.create_task(
            _heartbeat_watchdog(router),
            name="agent-heartbeat-watchdog",
        )
        logger.info("Agent 心跳看门狗已启动")
    except Exception:
        logger.exception("启动 Agent 心跳看门狗失败")
    yield
    if _agent_watchdog_task is not None:
        _agent_watchdog_task.cancel()
        try:
            await _agent_watchdog_task
        except asyncio.CancelledError:
            pass
        _agent_watchdog_task = None
        logger.info("Agent 心跳看门狗已停止")


app = FastAPI(title="momoqun", docs_url=None, redoc_url=None, lifespan=_app_lifespan)


# ---------------------------------------------------------------------------
# 内存环形日志缓冲：供 Web UI 实时展示运行日志（替代前端 mock）
# ---------------------------------------------------------------------------
_LOG_BUFFER: "collections.deque[Dict[str, str]]" = collections.deque(maxlen=500)
_LOG_BUFFER_LOCK = threading.Lock()


class _RingLogHandler(logging.Handler):
    """把日志记录写入内存环形缓冲，异常安全。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(getattr(record, "msg", ""))
        entry = {
            "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "name": record.name,
            "message": msg,
        }
        with _LOG_BUFFER_LOCK:
            _LOG_BUFFER.append(entry)


def _install_ring_log_handler() -> None:
    """把环形日志 handler 挂到 root logger（幂等）。"""
    root = logging.getLogger()
    if any(isinstance(h, _RingLogHandler) for h in root.handlers):
        return
    h = _RingLogHandler()
    h.setLevel(logging.INFO)
    root.addHandler(h)

# CORS：Web UI 跨域调 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    """API 鉴权：security.api_token 非空时要求 Bearer / X-Momoqun-Token。"""
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)
    if path == "/api/auth/status":
        return await call_next(request)
    if not auth_enabled():
        return await call_next(request)
    if not verify_token(get_token_from_request(request)):
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "未授权", "code": "unauthorized"},
        )
    return await call_next(request)


# 挂载 APK Agent WebSocket 路由（路线 C）
# 暴露：
#   - WS: ws://<host>:<port>/agent/{serial}    供 momoqun-agent.apk 连接
#   - HTTP GET /api/agents                     在线 agent 列表
try:
    from agent_router import mount_agent_routes, get_router
    mount_agent_routes(app)
except Exception:
    logger.exception("挂载 agent_router 失败（agent 模式不可用）")


@app.post("/api/test-rpc")
async def test_rpc(body: dict):
    serial = body.get("serial", "")
    method = body.get("method", "ping")
    params = body.get("params", {})
    timeout = body.get("timeout", 20.0)
    try:
        router = get_router()
        conn = router.get(serial)
        if conn is None:
            return {"ok": False, "error": f"agent {serial} not found"}
        result = await conn.call(method, params, timeout=timeout)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e), "type": type(e).__name__}


# 全局异常处理器
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": exc.detail, "code": "http_error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"ok": False, "error": "参数校验失败", "code": "validation_error", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("未捕获的异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": f"服务器内部错误: {exc}"},
    )


# ---------------------------------------------------------------------------
# 静态前端（Next.js 导出）
# ---------------------------------------------------------------------------
_WEBUI_DIR = os.path.join(BASE, "webui", "out")


@app.get("/")
async def serve_index():
    index_path = os.path.join(_WEBUI_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"error": "webui not built"}, status_code=404)


# 挂载静态资源（_next/, 404.html 等）
if os.path.isdir(_WEBUI_DIR):
    app.mount("/_next", StaticFiles(directory=os.path.join(_WEBUI_DIR, "_next")), name="next-assets")


# ---------------------------------------------------------------------------
# 设备管理器（唯一入口，管理所有设备）
# ---------------------------------------------------------------------------
_device_manager: Any = None
_device_manager_lock = threading.RLock()


def _get_device_manager():
    global _device_manager
    if _device_manager is None:
        with _device_manager_lock:
            if _device_manager is None:
                try:
                    from device_manager import DeviceManager
                except Exception as e:
                    logger.exception("加载 device_manager 失败")
                    raise RuntimeError(f"加载设备管理模块失败: {e}") from e
                settings = _load_settings()
                elements = _load_elements()
                _device_manager = DeviceManager([], settings, elements)
    return _device_manager


# ---------------------------------------------------------------------------
# 配置读写
# ---------------------------------------------------------------------------
def _load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return raw.get("config") or {}
    except FileNotFoundError:
        logger.warning("配置文件不存在: %s，使用默认配置", SETTINGS_PATH)
        return {}


def _save_settings(settings: dict) -> None:
    data = {"config": settings}
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    os.replace(tmp, SETTINGS_PATH)


def _load_elements() -> dict:
    try:
        with open(ELEMENTS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("元素配置文件不存在: %s，使用默认配置", ELEMENTS_PATH)
        return {}


# ---------------------------------------------------------------------------
# Master 地址探测（路线 C：把 ws://<本机IP>:<port> 显示在前端供复制）
# ---------------------------------------------------------------------------
def _is_usable_ipv4(addr: str) -> bool:
    """只排除回环 / APIPA(链路本地) / 非 IPv4。

    不按 is_private 过滤 —— IDC/群控机房常用非 RFC1918 网段（如 53.0.3.111），
    私网过滤会把唯一可用地址误删，导致前端空白。
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if ip.version != 4:
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        return False
    return True


def _detect_host_ipv4() -> List[str]:
    """探测本机可被模拟器访问的 IPv4，默认路由出口 IP 排第一。纯标准库、异常安全。"""
    candidates: List[str] = []

    # 1) 默认路由出口 IP：UDP connect 不真正发包，只让内核选源地址。
    #    单网卡机器上这就是模拟器能访问到宿主机的那个 IP（唯一正解）。
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        primary = sock.getsockname()[0]
        if _is_usable_ipv4(primary):
            candidates.append(primary)
    except Exception:
        logger.debug("默认路由出口 IP 探测失败", exc_info=True)
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    # 2) 主机名解析出的其它网卡（虚拟网卡等）作为备选。
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            if _is_usable_ipv4(addr) and addr not in candidates:
                candidates.append(addr)
    except Exception:
        logger.debug("getaddrinfo 探测失败", exc_info=True)

    return candidates


@app.get("/api/auth/status")
async def api_auth_status():
    """鉴权状态（公开）。Web UI 用于判断是否需输入 Token。"""
    return auth_status_payload()


@app.get("/api/master-address")
async def api_master_address(request: Request):
    """返回本机可供模拟器 Agent 连接的 master 地址。

    addresses 第一个为默认路由出口 IP（标“推荐”）；ws_urls 直接可复制下发。
    探测失败也不抛 500，返回空列表（符合项目“全程异常捕获”约定）。
    """
    try:
        addresses = _detect_host_ipv4()
    except Exception as e:
        logger.exception("探测本机地址失败: %s", e)
        addresses = []
    payload: Dict[str, Any] = {
        "addresses": addresses,
        "port": MASTER_PORT,
        "ws_urls": [f"ws://{ip}:{MASTER_PORT}" for ip in addresses],
        **auth_status_payload(),
    }
    if auth_enabled() and verify_token(get_token_from_request(request)):
        token = get_api_token()
        if token:
            payload["api_token"] = token
    return payload


# ---------------------------------------------------------------------------
# 设备管理 API
# ---------------------------------------------------------------------------
@app.get("/api/devices")
async def api_devices():
    """所有设备状态。"""
    return _get_device_manager().get_all_status()


@app.post("/api/devices/add")
async def api_devices_add(data: dict = None):
    """添加设备。body: {"serial": "127.0.0.1:5555", "name": "模拟器-1"}"""
    if not isinstance(data, dict):
        data = {}
    serial = (data.get("serial") or "").strip()
    name = (data.get("name") or "").strip() or serial
    if not serial:
        return JSONResponse({"ok": False, "error": "请提供 serial"}, status_code=400)

    mgr = _get_device_manager()
    dt = mgr.add_device(serial, name)
    if dt is None:
        return JSONResponse({"ok": False, "error": "设备已存在"}, status_code=400)
    logger.info("添加设备: %s (%s)", name, serial)
    return {"ok": True, "device": dt.snapshot()}


@app.post("/api/devices/remove")
async def api_devices_remove(data: dict = None):
    """移除设备。"""
    if not isinstance(data, dict):
        data = {}
    serial = (data.get("serial") or "").strip()
    if not serial:
        return JSONResponse({"ok": False, "error": "请提供 serial"}, status_code=400)
    mgr = _get_device_manager()
    if mgr.remove_device(serial):
        logger.info("移除设备: %s", serial)
        return {"ok": True}
    return JSONResponse({"ok": False, "error": "设备不存在"}, status_code=404)


@app.post("/api/devices/{action}")
async def api_devices_action(action: str, data: dict = None):
    """设备控制。action: start|stop|pause|resume|start_all|stop_all|pause_all|resume_all"""
    if not isinstance(data, dict):
        data = {}
    serial = data.get("serial", "")
    mgr = _get_device_manager()

    if action == "start_all":
        mgr.start_all()
    elif action == "stop_all":
        mgr.stop_all()
    elif action == "pause_all":
        mgr.pause_all()
    elif action == "resume_all":
        mgr.resume_all()
    elif action == "start":
        mgr.start_device(serial)
    elif action == "stop":
        mgr.stop_device(serial)
    elif action == "pause":
        mgr.pause_device(serial)
    elif action == "resume":
        mgr.resume_device(serial)
    else:
        return JSONResponse({"ok": False, "error": f"未知 action: {action}"}, status_code=400)
    return {"ok": True}


# ---------------------------------------------------------------------------
# 账号检测 API
# ---------------------------------------------------------------------------
@app.get("/api/account-check/status")
async def api_account_check_status():
    """聚合配置 + 所有设备的检测状态。供前端轮询。"""
    try:
        mgr = _get_device_manager()
        return mgr.get_account_check_status()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/account-check/config")
async def api_account_check_config(data: dict = None):
    """更新配置。body: {"enabled": bool, "interval_minutes": int, "on_abnormal": str}
    任一字段缺省表示不修改。会同时持久化到 settings.yaml。"""
    if not isinstance(data, dict):
        data = {}
    try:
        mgr = _get_device_manager()
        new_cfg = mgr.set_account_check_config(
            enabled=data.get("enabled"),
            interval_minutes=data.get("interval_minutes"),
            on_abnormal=data.get("on_abnormal"),
        )
        # 持久化到 settings.yaml
        try:
            s = _load_settings()
            ac = s.setdefault("account_check", {})
            ac["enabled"] = new_cfg["enabled"]
            ac["interval_minutes"] = new_cfg["interval_minutes"]
            ac["on_abnormal"] = new_cfg["on_abnormal"]
            _save_settings(s)
        except Exception:
            logger.exception("持久化 account_check 配置失败（运行时配置仍生效）")
        return {"ok": True, "config": new_cfg}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/account-check/trigger")
async def api_account_check_trigger(data: dict = None):
    """立即触发账号检测。
    body 空 → 对所有 running 设备触发。
    body 含 serial → 仅对该设备触发。"""
    if not isinstance(data, dict):
        data = {}
    serial = (data.get("serial") or "").strip()
    try:
        mgr = _get_device_manager()
        if serial:
            ok = mgr.trigger_account_check_one(serial)
            return {"ok": ok, "triggered": 1 if ok else 0}
        n = mgr.trigger_account_check_all()
        return {"ok": True, "triggered": n}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/account-check/dismiss")
async def api_account_check_dismiss(data: dict = None):
    """清除某台设备的异常标记（用户处理完毕后用）。
    如果设备是因检测被暂停的，自动恢复。"""
    if not isinstance(data, dict):
        data = {}
    serial = (data.get("serial") or "").strip()
    if not serial:
        return JSONResponse({"ok": False, "error": "请提供 serial"}, status_code=400)
    try:
        mgr = _get_device_manager()
        changed = mgr.dismiss_account_status(serial)
        return {"ok": True, "changed": changed}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# 聚合 API（减少 Web UI 轮询次数）
# ---------------------------------------------------------------------------
def _build_stats_payload(devices: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        from data.storage import aggregate_count_by_status
        counts = aggregate_count_by_status()
    except Exception as e:
        raise RuntimeError(str(e)) from e

    max_round = 0
    total_friends_this_round = 0
    for d in devices:
        try:
            max_round = max(max_round, int(d.get("round_number") or 0))
        except (ValueError, TypeError):
            pass
        try:
            total_friends_this_round += int(d.get("friends_this_round") or 0)
        except (ValueError, TypeError):
            pass

    return {
        "friends": counts,
        "round_number": max_round,
        "friends_this_round": total_friends_this_round,
        "device_count": len(devices),
    }


@app.get("/api/dashboard")
async def api_dashboard():
    """设备 + 统计 + 账号检测 + 在线 Agent 一次返回。"""
    try:
        mgr = _get_device_manager()
        devices = mgr.get_all_status()
        stats = _build_stats_payload(devices)
        account_check = mgr.get_account_check_status()
        agents: List[Dict[str, Any]] = []
        try:
            agents = get_router().snapshot()
        except Exception:
            logger.debug("读取 agent 快照失败", exc_info=True)
        return {
            "devices": devices,
            "stats": stats,
            "account_check": account_check,
            "agents": agents,
        }
    except Exception as e:
        logger.exception("dashboard API 失败")
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# 统计 API
# ---------------------------------------------------------------------------
@app.get("/api/stats")
async def api_stats():
    """返回好友统计 + 会话状态快照（聚合所有 per-device 文件）。"""
    try:
        mgr = _get_device_manager()
        return _build_stats_payload(mgr.get_all_status())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# 日志 API
# ---------------------------------------------------------------------------
@app.get("/api/logs")
async def api_logs(limit: int = 200):
    """返回最近的运行日志（内存环形缓冲）。供 Web UI 轮询展示。"""
    try:
        with _LOG_BUFFER_LOCK:
            items = list(_LOG_BUFFER)
        if limit and limit > 0:
            items = items[-limit:]
        return {"logs": items}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# 配置 API
# ---------------------------------------------------------------------------
@app.get("/api/config")
async def api_get_config():
    return _load_settings()


@app.put("/api/config")
async def api_set_config(data: dict = None):
    if not isinstance(data, dict):
        data = {}
    try:
        from utils.config_merge import deep_merge

        patch = data.get("config") or data
        merged = deep_merge(_load_settings(), patch)
        _save_settings(merged)
        mgr = _get_device_manager()
        mgr.reload_config(merged, _load_elements())
        load_security_config(merged)
        return {"ok": True, "config": merged}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# 关闭 API
# ---------------------------------------------------------------------------
_CLEANUP_LOCK = threading.Lock()
_CLEANUP_DONE = False


def _archive_and_clear_all_devices() -> None:
    """对所有 per-device friends/state 归档+清零，幂等。"""
    global _CLEANUP_DONE
    with _CLEANUP_LOCK:
        if _CLEANUP_DONE:
            return
        try:
            from data.storage import archive_and_clear_all
            from core.message_pool import archive_and_clear_all_state

            res_friends = archive_and_clear_all()
            logger.info("friends 归档完成: %d 台设备", len(res_friends))
            for serial, path in res_friends.items():
                if path:
                    logger.info("  [%s] -> %s", serial, path)

            res_state = archive_and_clear_all_state()
            logger.info("state 归档完成: %d 台设备", len(res_state))
        except Exception:
            logger.exception("归档清零失败（继续退出）")
        _CLEANUP_DONE = True


# 进程级 atexit 兜底（PyInstaller / 终端 Ctrl+C 都会触发）
atexit.register(_archive_and_clear_all_devices)


@app.post("/api/shutdown")
async def api_shutdown():
    """优雅关闭：停止所有设备线程，归档清零好友数据，退出。"""
    logger.info("收到 shutdown 请求，清理中...")
    try:
        mgr = _get_device_manager()
        mgr.stop_all()
    except Exception as e:
        logger.warning("停止设备失败: %s", e)

    _archive_and_clear_all_devices()

    def _do_exit():
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=_do_exit, daemon=True).start()
    return {"ok": True, "message": "正在关闭..."}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    from utils.helpers import setup_logging
    setup_logging()
    _install_ring_log_handler()

    import argparse
    parser = argparse.ArgumentParser(description="momoqun Server")
    parser.add_argument("--port", type=int, default=5100, help="Web 端口")
    args = parser.parse_args()

    global MASTER_PORT
    MASTER_PORT = args.port

    def cleanup():
        logger.info("Server 退出中...")
        if _device_manager:
            try:
                _device_manager.stop_all()
            except Exception:
                logger.exception("stop_all 失败")
        _archive_and_clear_all_devices()

    signal.signal(signal.SIGINT, lambda s, f: cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: cleanup() or sys.exit(0))

    logger.info("momoqun 启动: http://localhost:%d", args.port)
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()

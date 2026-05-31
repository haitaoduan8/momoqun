"""momoqun 服务器：FastAPI + Web UI + 内置设备管理

用法:
    python server.py --port 5100
"""

from __future__ import annotations

import atexit
import collections
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List

import uvicorn
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Windows: 禁止子进程弹出控制台窗口
_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0

# PyInstaller 打包后资源路径：spec 里把 assets/* 放到了 ./assets/
def _get_assets_dir() -> str:
    """返回 uiautomator2 资源目录（兼容 PyInstaller 和开发模式）。"""
    if getattr(sys, "frozen", False):
        # COLLECT 模式下资源在 exe 同级目录，不用 _MEIPASS（有时指向 _internal）
        base = os.path.dirname(sys.executable)
        path = os.path.join(base, "assets")
        if os.path.isdir(path):
            return path
        # 回退：_MEIPASS + assets
        path = os.path.join(sys._MEIPASS, "assets")
        if os.path.isdir(path):
            return path
        return sys._MEIPASS
    # 开发模式：从 uiautomator2 包里找
    import uiautomator2 as _u2
    return os.path.join(os.path.dirname(_u2.__file__), "assets")
# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE, "config", "settings.yaml")
ELEMENTS_PATH = os.path.join(BASE, "config", "elements.yaml")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="momoqun", docs_url=None, redoc_url=None)
logger = logging.getLogger("server")


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

# CORS：Flet Web 在 localhost:8550 调 API 需要跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 挂载 APK Agent WebSocket 路由（路线 C）
# 暴露：
#   - WS: ws://<host>:<port>/agent/{serial}    供 momoqun-agent.apk 连接
#   - HTTP GET /api/agents                     在线 agent 列表
try:
    from agent_router import mount_agent_routes
    mount_agent_routes(app)
except Exception:
    logger.exception("挂载 agent_router 失败（agent 模式不可用）")


# 全局异常处理器：确保所有错误都返回 JSON（而不是 HTML 500 页面）
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("未捕获的异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": f"服务器内部错误: {exc}"},
    )


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
# ADB API
# ---------------------------------------------------------------------------
@app.get("/api/adb/devices")
async def api_adb_devices():
    try:
        result = subprocess.run(
            ["adb", "devices", "-l"], capture_output=True, text=True, timeout=10,
            creationflags=_WIN_FLAGS,
        )
        lines = (result.stdout or "").strip().split("\n")[1:]
        devices = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                info = " ".join(parts[2:]) if len(parts) > 2 else ""
                devices.append({"serial": serial, "info": info, "state": "device"})
        return {"devices": devices}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/adb/connect")
async def api_adb_connect(data: dict = None):
    if not isinstance(data, dict):
        data = {}
    addr = (data.get("address") or "").strip()
    if not addr:
        return JSONResponse({"ok": False, "error": "请提供 address"}, status_code=400)
    try:
        result = subprocess.run(
            ["adb", "connect", addr], capture_output=True, text=True, timeout=15,
            creationflags=_WIN_FLAGS,
        )
        output = (result.stdout or "").strip()
        # adb connect 成功时输出包含 "connected"（包括 "already connected"）
        ok = "connected" in output.lower()
        return {"ok": ok, "output": output}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/adb/disconnect")
async def api_adb_disconnect(data: dict = None):
    if not isinstance(data, dict):
        data = {}
    addr = (data.get("address") or "").strip()
    if not addr:
        return JSONResponse({"ok": False, "error": "请提供 address"}, status_code=400)
    try:
        subprocess.run(
            ["adb", "disconnect", addr], capture_output=True, text=True, timeout=10,
            creationflags=_WIN_FLAGS,
        )
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/adb/init")
async def api_adb_init(data: dict = None):
    """初始化设备：安装 ATX agent (含 ADB Keyboard) + 推送 u2.jar。
    用纯 adb 命令，不依赖 Python，PyInstaller EXE 环境可用。"""
    if not isinstance(data, dict):
        data = {}
    serial = (data.get("serial") or "").strip()
    if not serial:
        return JSONResponse({"ok": False, "error": "请提供 serial"}, status_code=400)

    assets_dir = _get_assets_dir()
    apk_path = os.path.join(assets_dir, "app-uiautomator.apk")
    jar_path = os.path.join(assets_dir, "u2.jar")

    if not os.path.isfile(apk_path):
        return JSONResponse({"ok": False, "error": f"APK 文件不存在: {apk_path}"}, status_code=500)
    if not os.path.isfile(jar_path):
        return JSONResponse({"ok": False, "error": f"JAR 文件不存在: {jar_path}"}, status_code=500)

    outputs = []

    # 1. 安装 ATX agent APK（包含 ADB Keyboard IME）
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "install", "-r", apk_path],
            capture_output=True, text=True, timeout=120,
            creationflags=_WIN_FLAGS,
        )
        out = (result.stdout or "").strip() + "\n" + (result.stderr or "").strip()
        outputs.append(f"[APK] {out.strip()}")
        if result.returncode != 0 and "Success" not in out:
            return {"ok": False, "output": "\n".join(outputs),
                    "error": f"APK 安装失败 (code={result.returncode})"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"安装 APK 失败: {e}"}, status_code=500)

    # 2. 推送 u2.jar 到设备
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "push", jar_path, "/data/local/tmp/u2.jar"],
            capture_output=True, text=True, timeout=30,
            creationflags=_WIN_FLAGS,
        )
        out = (result.stdout or "").strip()
        outputs.append(f"[JAR] {out}")
    except Exception as e:
        outputs.append(f"[JAR] 推送失败: {e}")

    # 3. 启用并切换到 ADB Keyboard（雷电等模拟器需要 ime enable 先）
    ime_id = "com.github.uiautomator/.AdbKeyboard"
    try:
        subprocess.run(
            ["adb", "-s", serial, "shell", "ime", "enable", ime_id],
            capture_output=True, text=True, timeout=10,
            creationflags=_WIN_FLAGS,
        )
        result = subprocess.run(
            ["adb", "-s", serial, "shell", "ime", "set", ime_id],
            capture_output=True, text=True, timeout=10,
            creationflags=_WIN_FLAGS,
        )
        out = (result.stdout or "").strip() or (result.stderr or "").strip()
        outputs.append(f"[IME] {out or '已切换'}")
    except Exception as e:
        outputs.append(f"[IME] 切换失败: {e}")

    return {"ok": True, "output": "\n".join(outputs)}


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
# 统计 API
# ---------------------------------------------------------------------------
@app.get("/api/stats")
async def api_stats():
    """返回好友统计 + 会话状态快照（聚合所有 per-device 文件）。"""
    try:
        from data.storage import aggregate_count_by_status
        counts = aggregate_count_by_status()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    mgr = _get_device_manager()
    devices = mgr.get_all_status()

    # 聚合会话状态（取最大轮次）
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
        new_cfg = data.get("config") or data
        _save_settings(new_cfg)
        mgr = _get_device_manager()
        mgr.reload_config(new_cfg, _load_elements())
        return {"ok": True}
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

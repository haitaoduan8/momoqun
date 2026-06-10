"""Agent APK 安装与 SET_CONFIG 下发。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from agent_router import AgentRouter

from ops.adb_ops import list_online_serials, run_adb

logger = logging.getLogger(__name__)

CONFIG_ACTION = "com.momoqun.agent.SET_CONFIG"
CONFIG_RECEIVER = "com.momoqun.agent/.service.ConfigReceiver"
DEFAULT_APK_PATH = "agent-bundle/app-release.apk"


def adb_serial_to_agent_serial(adb_serial: str) -> str:
    """ADB serial → Agent/master serial（冒号转下划线）。"""
    return AgentRouter.normalize_serial(adb_serial.strip())


def agent_serial_to_adb_serial(agent_serial: str) -> str:
    """Agent/master serial → ADB serial（``127.0.0.1_5555`` → ``127.0.0.1:5555``）。"""
    s = (agent_serial or "").strip()
    if ":" in s:
        return s
    if "_" in s:
        host, tail = s.rsplit("_", 1)
        if tail.isdigit():
            return f"{host}:{tail}"
    return s


def build_set_config_command(
    adb_serial: str,
    master_url: str,
    agent_serial: str,
    *,
    autostart: bool = True,
) -> List[str]:
    """拼装 adb shell am broadcast 参数列表（供测试与执行）。"""
    return [
        "-s",
        adb_serial,
        "shell",
        "am",
        "broadcast",
        "-a",
        CONFIG_ACTION,
        "--es",
        "master_url",
        master_url.strip(),
        "--es",
        "serial",
        agent_serial.strip(),
        "--ez",
        "autostart",
        "true" if autostart else "false",
        "-n",
        CONFIG_RECEIVER,
    ]


def install_agent_apk(adb_serial: str, apk_path: str) -> Tuple[bool, str]:
    if not os.path.isfile(apk_path):
        return False, f"APK 不存在: {apk_path}"
    _, stderr, rc = run_adb(
        ["-s", adb_serial, "install", "-r", "-g", apk_path],
        timeout=120,
    )
    if rc == 0:
        return True, ""
    return False, (stderr or "install 失败").strip()


def deploy_agent_config(
    adb_serial: str,
    master_url: str,
    *,
    agent_serial: Optional[str] = None,
    autostart: bool = True,
) -> Dict[str, Any]:
    """向单台设备 broadcast SET_CONFIG。"""
    agent_serial = agent_serial or adb_serial_to_agent_serial(adb_serial)
    try:
        args = build_set_config_command(
            adb_serial, master_url, agent_serial, autostart=autostart,
        )
        stdout, stderr, rc = run_adb(args, timeout=30)
        ok = rc == 0
        if not ok:
            logger.warning(
                "SET_CONFIG 失败 adb=%s agent_serial=%s rc=%d stderr=%s",
                adb_serial, agent_serial, rc, stderr,
            )
        return {
            "adb_serial": adb_serial,
            "agent_serial": agent_serial,
            "master_url": master_url,
            "ok": ok,
            "step": "config",
            "stdout": (stdout or "").strip() or None,
            "error": None if ok else (stderr or "broadcast 失败").strip(),
        }
    except Exception as exc:
        logger.exception("deploy_agent_config 异常 adb=%s", adb_serial)
        return {
            "adb_serial": adb_serial,
            "agent_serial": agent_serial,
            "ok": False,
            "step": "config",
            "error": str(exc),
        }


def deploy_many(
    adb_serials: List[str],
    master_url: str,
    *,
    install_apk: bool = False,
    apk_path: Optional[str] = None,
    autostart: bool = True,
) -> Dict[str, Any]:
    """批量安装（可选）并下发配置。"""
    results: List[Dict[str, Any]] = []
    resolved_apk: Optional[str] = None
    if install_apk:
        resolved_apk = apk_path or DEFAULT_APK_PATH
        if not os.path.isabs(resolved_apk):
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            resolved_apk = os.path.join(base, resolved_apk)

    for adb_serial in adb_serials:
        entry: Dict[str, Any] = {
            "adb_serial": adb_serial,
            "agent_serial": adb_serial_to_agent_serial(adb_serial),
        }
        if install_apk and resolved_apk:
            ok, err = install_agent_apk(adb_serial, resolved_apk)
            entry["install_ok"] = ok
            if not ok:
                entry["ok"] = False
                entry["step"] = "install"
                entry["error"] = err
                results.append(entry)
                continue

        cfg = deploy_agent_config(
            adb_serial,
            master_url,
            agent_serial=entry["agent_serial"],
            autostart=autostart,
        )
        entry.update(cfg)
        results.append(entry)

    success = sum(1 for r in results if r.get("ok"))
    return {
        "ok": True,
        "master_url": master_url,
        "results": results,
        "success": success,
        "fail": len(results) - success,
    }


def resolve_target_serials(requested: Optional[List[str]]) -> List[str]:
    """空列表 → 全部在线 adb device。"""
    if requested:
        return [s.strip() for s in requested if s and s.strip()]
    return list_online_serials()

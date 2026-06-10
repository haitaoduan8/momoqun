"""ADB 子进程封装（提炼自 shanghao/adb_push_gui.py）。"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_adb_path() -> str:
    """优先 repo 内 platform-tools，否则 PATH 中的 adb。"""
    adb_name = "adb.exe" if sys.platform == "win32" else "adb"
    candidates = [
        os.path.join(_BASE, "platform-tools", adb_name),
        os.path.join(_BASE, "agent-bundle", "platform-tools", adb_name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return adb_name


def run_adb(args: List[str], timeout: float = 30) -> Tuple[str, str, int]:
    """执行 adb 命令，返回 (stdout, stderr, returncode)。"""
    adb_path = get_adb_path()
    adb_cwd = os.path.dirname(adb_path) if os.path.isfile(adb_path) else None
    kwargs: Dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "cwd": adb_cwd,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    try:
        result = subprocess.run([adb_path] + args, **kwargs)
        return result.stdout or "", result.stderr or "", result.returncode
    except subprocess.TimeoutExpired:
        logger.warning("adb 命令超时: %s", args[:6])
        return "", "命令超时", 1
    except FileNotFoundError:
        logger.exception("未找到 adb")
        return "", "未找到 adb，请确认 platform-tools 或 PATH", 1
    except Exception:
        logger.exception("adb 执行异常 args=%s", args[:6])
        return "", "adb 执行异常", 1


def get_device_model(adb_serial: str) -> str:
    stdout, _, rc = run_adb(["-s", adb_serial, "shell", "getprop", "ro.product.model"])
    if rc != 0:
        return "未知型号"
    return (stdout or "").strip() or "未知型号"


def list_devices() -> List[Dict[str, str]]:
    """返回 [{adb_serial, model, state}]，仅 state=device 的条目含 model。"""
    stdout, stderr, rc = run_adb(["devices"])
    if rc != 0:
        logger.warning("adb devices 失败: %s", stderr)
        return []

    devices: List[Dict[str, str]] = []
    for line in (stdout or "").strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        adb_serial, state = parts[0], parts[1]
        entry = {"adb_serial": adb_serial, "state": state, "model": ""}
        if state == "device":
            try:
                entry["model"] = get_device_model(adb_serial)
            except Exception:
                logger.debug("get_device_model 失败 serial=%s", adb_serial, exc_info=True)
        devices.append(entry)
    return devices


def launch_app(adb_serial: str, package: str, activity: str = "") -> Tuple[str, str, int]:
    """启动应用。未指定 activity 时使用 monkey 拉起主界面。"""
    if activity:
        return run_adb(
            ["-s", adb_serial, "shell", "am", "start", "-n", f"{package}/{activity}"],
            timeout=15,
        )
    return run_adb(
        [
            "-s",
            adb_serial,
            "shell",
            "monkey",
            "-p",
            package,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
        timeout=15,
    )


def list_online_serials() -> List[str]:
    return [d["adb_serial"] for d in list_devices() if d.get("state") == "device"]


def shell_mkdir_p(adb_serial: str, remote_dir: str) -> bool:
    _, stderr, rc = run_adb(["-s", adb_serial, "shell", "mkdir", "-p", remote_dir])
    if rc != 0:
        logger.warning("mkdir 失败 serial=%s dir=%s: %s", adb_serial, remote_dir, stderr)
    return rc == 0


def push_file_to_device(
    adb_serial: str,
    local_path: str,
    remote_path: str,
    *,
    timeout: float = 300,
) -> Tuple[bool, str]:
    """推送本地文件到设备 remote_path（完整路径含文件名）。"""
    _, stderr, rc = run_adb(
        ["-s", adb_serial, "push", local_path, remote_path],
        timeout=timeout,
    )
    if rc == 0:
        return True, ""
    return False, (stderr or "push 失败").strip()


def clear_remote_dir(adb_serial: str, remote_dir: str) -> Tuple[bool, str]:
    """删除模拟器目标目录内的所有文件（不删目录本身）。"""
    rd = (remote_dir or "").strip().rstrip("/")
    if not rd:
        return False, "remote_dir 为空"
    try:
        _, stderr, rc = run_adb(
            ["-s", adb_serial, "shell", "rm", "-f", f"{rd}/*"],
            timeout=60,
        )
        if rc != 0:
            return False, (stderr or "rm 失败").strip()
        return True, ""
    except Exception as exc:
        logger.exception("clear_remote_dir 异常 serial=%s", adb_serial)
        return False, str(exc)


def push_single_replace(
    adb_serial: str,
    local_file: str,
    remote_dir: str,
) -> Dict[str, Any]:
    """单文件替换：删旧后推送。"""
    filename = os.path.basename(local_file)
    remote_file = f"{remote_dir.rstrip('/')}/{filename}"
    try:
        shell_mkdir_p(adb_serial, remote_dir)
        run_adb(["-s", adb_serial, "shell", "rm", "-f", remote_file])
        ok, err = push_file_to_device(adb_serial, local_file, remote_file)
        return {
            "adb_serial": adb_serial,
            "ok": ok,
            "file": filename,
            "remote": remote_file,
            "error": err or None,
        }
    except Exception as exc:
        logger.exception("push_single_replace 异常 serial=%s", adb_serial)
        return {
            "adb_serial": adb_serial,
            "ok": False,
            "file": filename,
            "error": str(exc),
        }


def preview_batch_pairing(local_dir: str, serials: List[str]) -> Dict[str, Any]:
    """批量 1:1 配对预览。"""
    if not os.path.isdir(local_dir):
        return {"ok": False, "error": "本地文件夹不存在", "pairs": []}

    files = sorted(
        os.path.join(local_dir, name)
        for name in os.listdir(local_dir)
        if os.path.isfile(os.path.join(local_dir, name))
    )
    pair_count = min(len(files), len(serials))
    pairs = [
        {
            "adb_serial": serials[i],
            "file": os.path.basename(files[i]),
            "local_path": files[i],
        }
        for i in range(pair_count)
    ]
    return {
        "ok": True,
        "file_count": len(files),
        "device_count": len(serials),
        "pair_count": pair_count,
        "extra_files": max(0, len(files) - len(serials)),
        "extra_devices": max(0, len(serials) - len(files)),
        "pairs": pairs,
    }


def push_batch_pairing(
    local_dir: str,
    serials: List[str],
    remote_dir: str,
) -> Dict[str, Any]:
    """文件夹内文件与设备 1:1 推送（不重复）。"""
    preview = preview_batch_pairing(local_dir, serials)
    if not preview.get("ok"):
        return {"ok": False, "error": preview.get("error", "预览失败"), "results": []}

    results: List[Dict[str, Any]] = []
    for pair in preview.get("pairs") or []:
        adb_serial = pair["adb_serial"]
        local_path = pair["local_path"]
        filename = pair["file"]
        remote_file = f"{remote_dir.rstrip('/')}/{filename}"
        try:
            shell_mkdir_p(adb_serial, remote_dir)
            ok, err = push_file_to_device(adb_serial, local_path, remote_file)
            results.append({
                "adb_serial": adb_serial,
                "ok": ok,
                "file": filename,
                "remote": remote_file,
                "error": err or None,
            })
        except Exception as exc:
            logger.exception("batch push 异常 serial=%s", adb_serial)
            results.append({
                "adb_serial": adb_serial,
                "ok": False,
                "file": filename,
                "error": str(exc),
            })

    success = sum(1 for r in results if r.get("ok"))
    return {
        "ok": True,
        "preview": preview,
        "results": results,
        "success": success,
        "fail": len(results) - success,
    }

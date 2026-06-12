"""本地换号文件夹的全局用量登记（多模拟器共享，已用文件不再分配）。"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

_DATA_ROOT = "data"
_POOL_PATH = os.path.join(_DATA_ROOT, "file_pool.json")
_LOCK = threading.RLock()
_logger = logging.getLogger(__name__)


def _read_pool() -> Dict[str, Any]:
    try:
        with open(_POOL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        _logger.exception("读取 file_pool 失败")
        return {}


def _write_pool(data: Dict[str, Any]) -> None:
    os.makedirs(_DATA_ROOT, exist_ok=True)
    tmp = f"{_POOL_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _POOL_PATH)


def list_local_files(local_dir: str) -> List[str]:
    if not os.path.isdir(local_dir):
        return []
    return sorted(
        os.path.join(local_dir, name)
        for name in os.listdir(local_dir)
        if os.path.isfile(os.path.join(local_dir, name))
        and not name.startswith(".")
    )


def get_pool_status(local_dir: str = "") -> Dict[str, Any]:
    """返回已用文件列表与剩余可分配数量。"""
    with _LOCK:
        data = _read_pool()
        used = list(data.get("used_files") or [])
        tracked_dir = str(data.get("local_dir") or "")
        dir_for_count = local_dir.strip() or tracked_dir
        total = len(list_local_files(dir_for_count)) if dir_for_count else 0
        return {
            "local_dir": tracked_dir,
            "used_files": used,
            "used_count": len(used),
            "total_files": total,
            "remaining": max(0, total - len(used)),
            "assignments": dict(data.get("assignments") or {}),
        }


def claim_next_file(local_dir: str, serial: str) -> Tuple[Optional[str], str]:
    """为设备领取下一个未使用的本地文件。返回 (local_path, error)。"""
    local_dir = (local_dir or "").strip()
    serial = (serial or "").strip()
    if not local_dir:
        return None, "未配置本地文件夹"
    if not os.path.isdir(local_dir):
        return None, f"本地文件夹不存在: {local_dir}"

    with _LOCK:
        data = _read_pool()
        if data.get("local_dir") and data.get("local_dir") != local_dir:
            _logger.info(
                "file_pool: local_dir 变更 %s -> %s，保留已用记录",
                data.get("local_dir"),
                local_dir,
            )
        data["local_dir"] = local_dir
        used = set(data.get("used_files") or [])
        files = list_local_files(local_dir)
        for path in files:
            name = os.path.basename(path)
            if name in used:
                continue
            used.add(name)
            data["used_files"] = sorted(used)
            assignments = dict(data.get("assignments") or {})
            assignments[serial] = name
            data["assignments"] = assignments
            _write_pool(data)
            _logger.info("file_pool: 分配 %s → %s", name, serial)
            return path, ""

    return None, "本地文件夹内无可用未使用文件"

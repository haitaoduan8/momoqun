"""发完动态后招呼未达阈值的账号文件名登记（持久化，仅手动清空）。"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List

_DATA_ROOT = "data"
_REGISTRY_PATH = os.path.join(_DATA_ROOT, "low_greet_accounts.json")
_LOCK = threading.RLock()
_logger = logging.getLogger(__name__)


def _read_registry() -> Dict[str, Any]:
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"entries": []}
    except FileNotFoundError:
        return {"entries": []}
    except Exception:
        _logger.exception("读取 low_greet_accounts 失败")
        return {"entries": []}


def _write_registry(data: Dict[str, Any]) -> None:
    os.makedirs(_DATA_ROOT, exist_ok=True)
    tmp = f"{_REGISTRY_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _REGISTRY_PATH)


def list_entries() -> List[Dict[str, Any]]:
    with _LOCK:
        data = _read_registry()
        entries = data.get("entries") or []
        return list(entries) if isinstance(entries, list) else []


def add_entry(
    filename: str,
    *,
    serial: str = "",
    device_name: str = "",
) -> bool:
    """登记低招呼账号；同一文件名不重复添加。"""
    filename = (filename or "").strip()
    if not filename:
        return False
    with _LOCK:
        data = _read_registry()
        entries = list(data.get("entries") or [])
        for item in entries:
            if isinstance(item, dict) and item.get("filename") == filename:
                return False
        entries.append(
            {
                "filename": filename,
                "serial": serial,
                "device_name": device_name,
                "reported_at": time.time(),
            }
        )
        data["entries"] = entries
        _write_registry(data)
        _logger.info("low_greet: 登记 %s (serial=%s)", filename, serial)
        return True


def clear_all() -> int:
    """手动清空全部登记，返回清除条数。"""
    with _LOCK:
        data = _read_registry()
        entries = data.get("entries") or []
        count = len(entries) if isinstance(entries, list) else 0
        data["entries"] = []
        _write_registry(data)
        _logger.info("low_greet: 手动清空 %d 条", count)
        return count

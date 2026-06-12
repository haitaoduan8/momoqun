"""发动态后超时仍无足够招呼：登记账号文件名供前端展示。"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from data.low_greet_registry import add_entry


def _first_batch_min_count(settings: dict) -> int:
    cfg = (settings or {}).get("approve_greeting") or {}
    try:
        return max(0, int(cfg.get("first_batch_min_count", 3)))
    except (TypeError, ValueError):
        return 3


def _low_greet_wait_minutes(settings: dict) -> float:
    cfg = (settings or {}).get("approve_greeting") or {}
    try:
        return max(1.0, float(cfg.get("low_greet_wait_minutes", 5)))
    except (TypeError, ValueError):
        return 5.0


def _post_dynamic_swap_enabled(settings: dict) -> bool:
    ac_cfg = (settings or {}).get("account_check") or {}
    try:
        return float(ac_cfg.get("post_dynamic_no_greet_swap_minutes", 5)) > 0
    except (TypeError, ValueError):
        return True


def maybe_report_low_greet(
    *,
    greeter: Any,
    storage: Any,
    settings: dict,
    serial: str,
    device_name: str = "",
    logger: Optional[logging.Logger] = None,
) -> bool:
    """发完动态满 N 分钟且招呼未达首批阈值时，登记当前号文件名（每号一次）。"""
    log = logger or logging.getLogger("low_greet_watch")
    try:
        if _post_dynamic_swap_enabled(settings):
            return False
        if storage.get_device_state_flag("first_greet_batch_done", False):
            return False
        if storage.get_device_state_flag("low_greet_reported", False):
            return False

        post_at = storage.get_device_state_field("post_dynamic_at", 0)
        try:
            post_at_f = float(post_at or 0)
        except (TypeError, ValueError):
            post_at_f = 0.0
        if post_at_f <= 0:
            return False

        wait_min = _low_greet_wait_minutes(settings)
        if time.time() - post_at_f < wait_min * 60.0:
            return False

        min_count = _first_batch_min_count(settings)
        try:
            badge = int(greeter.scan_badge() or 0)
        except Exception:
            log.exception("low_greet scan_badge 异常")
            badge = 0

        if badge >= min_count:
            return False

        filename = str(
            storage.get_device_state_field("current_account_filename", "") or ""
        ).strip()
        if not filename:
            from data.file_pool import get_pool_status

            assignments = get_pool_status().get("assignments") or {}
            filename = str(assignments.get(serial) or "").strip()
        if not filename:
            log.warning("low_greet: 无文件名可登记 serial=%s", serial)
            return False

        if add_entry(filename, serial=serial, device_name=device_name):
            storage.set_device_state_flag("low_greet_reported", True)
            log.warning(
                "low_greet: %s 发完动态 %.0f 分钟后招呼 %d < %d，已登记",
                filename,
                wait_min,
                badge,
                min_count,
            )
            return True
        return False
    except Exception:
        log.exception("maybe_report_low_greet 异常 serial=%s", serial)
        return False

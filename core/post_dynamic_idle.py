"""发动态后无招呼超时：直接换号（不跑账号检测）。"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional


def _post_dynamic_swap_minutes(settings: dict) -> float:
    ac_cfg = (settings or {}).get("account_check") or {}
    try:
        return float(ac_cfg.get("post_dynamic_no_greet_swap_minutes", 5))
    except (TypeError, ValueError):
        return 5.0


def wait_after_post_dynamic_no_greet(
    *,
    greeter: Any,
    storage: Any,
    settings: dict,
    should_stop: Callable[[], bool],
    should_pause: Callable[[], bool],
    on_swap_account: Callable[[str], bool],
    logger: Optional[logging.Logger] = None,
) -> None:
    """发动态后周期性扫角标；连续 N 分钟无招呼则直接换号。"""
    log = logger or logging.getLogger("post_dynamic_idle")
    swap_min = _post_dynamic_swap_minutes(settings)
    if swap_min <= 0:
        return

    scan_s = float((settings or {}).get("greet_scan_interval_s") or 5.0)

    try:
        post_at = storage.get_device_state_field("post_dynamic_at", 0)
        post_at_f = float(post_at or 0)
    except (TypeError, ValueError):
        post_at_f = 0.0
    if post_at_f <= 0:
        return

    log.info(
        "发动态后无招呼换号：每 %.1fs 扫描，%.0f 分钟无招呼则直接换号",
        scan_s,
        swap_min,
    )
    swap_deadline = post_at_f + swap_min * 60.0

    while not should_stop():
        while should_pause() and not should_stop():
            time.sleep(0.3)

        try:
            badge = int(greeter.scan_badge() or 0)
        except Exception:
            log.exception("post_dynamic_idle scan_badge 异常")
            badge = 0

        if badge > 0:
            log.info("发动态后检测到 %d 个招呼，结束等待", badge)
            return

        if time.time() >= swap_deadline:
            log.warning(
                "发动态后已连续 %.0f 分钟无招呼，直接换号（不检测）",
                swap_min,
            )
            on_swap_account("发动态后无招呼")
            return

        time.sleep(max(0.5, scan_s))

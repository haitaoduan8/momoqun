"""邀请进群后的空闲等待：无招呼超时 → 账号检测 → 违规换号。"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from core.account_check import AccountCheckResult, run_account_check


def wait_after_invite_no_greet(
    *,
    greeter: Any,
    driver: Any,
    elements: dict,
    settings: dict,
    storage: Any,
    serial: str,
    should_stop: Callable[[], bool],
    should_pause: Callable[[], bool],
    on_account_status: Callable[[AccountCheckResult], None],
    on_swap_account: Callable[[], bool],
    logger: Optional[logging.Logger] = None,
) -> None:
    """已邀请过好友且本轮无新招呼时：周期性扫描，超时后做账号检测。"""
    log = logger or logging.getLogger("greet_idle")
    ac_cfg = (settings or {}).get("account_check") or {}
    try:
        idle_min = max(1.0, float(ac_cfg.get("idle_after_invite_minutes", 5)))
    except (TypeError, ValueError):
        idle_min = 5.0
    scan_s = float((settings or {}).get("greet_scan_interval_s") or 5.0)
    timeout = float(ac_cfg.get("detect_timeout_sec") or 8.0)

    log.info(
        "邀请后空闲等待：每 %.1fs 扫描招呼，%.0f 分钟无招呼则检测账号",
        scan_s,
        idle_min,
    )
    idle_deadline = time.monotonic() + idle_min * 60.0

    while not should_stop():
        while should_pause() and not should_stop():
            time.sleep(0.3)

        try:
            badge = greeter.scan_badge()
        except Exception:
            log.exception("空闲等待 scan_badge 异常")
            badge = 0

        if badge > 0:
            log.info("空闲等待结束：检测到 %d 个招呼", badge)
            return

        if time.monotonic() >= idle_deadline:
            log.info("已连续 %.0f 分钟无招呼，开始账号检测", idle_min)
            try:
                result = run_account_check(
                    driver,
                    elements,
                    detect_timeout_sec=timeout,
                    logger=log,
                )
            except Exception:
                log.exception("空闲账号检测异常")
                result = AccountCheckResult.ERROR

            on_account_status(result)

            if result is AccountCheckResult.OK:
                log.info("账号正常，继续等待招呼")
                idle_deadline = time.monotonic() + idle_min * 60.0
            elif result is AccountCheckResult.ABNORMAL:
                log.warning("账号违规，执行换号文件")
                on_swap_account()
                return
            else:
                log.warning("账号检测未确认（%s），继续等待", result.value)
                idle_deadline = time.monotonic() + idle_min * 60.0

        time.sleep(max(0.5, scan_s))

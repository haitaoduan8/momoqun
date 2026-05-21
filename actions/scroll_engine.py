"""Fling-free scrolling helpers for the gift panel."""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

_STEPS = 48
_END_HOLD_S = 0.28
_MIN_DURATION_MS = 320
_DURATION_PX_COEF = 0.55


def _ease_out_cubic(t: float) -> float:
    """Map t in [0, 1] to an ease-out distance ratio."""
    u = 1.0 - t
    return 1.0 - u * u * u


def smooth_scroll_up(
    dev_d,
    list_bounds: Dict[str, int],
    swipe_pixels: int,
    steps: int = _STEPS,
    end_hold_s: float = _END_HOLD_S,
    bottom_padding: int = 36,
    top_padding: int = 40,
    duration_px_coef: Optional[float] = None,
    min_duration_ms: Optional[int] = None,
    end_floor_y: Optional[int] = None,
) -> bool:
    """Drag upward inside ``list_bounds`` with a decelerating touch chain.

    The final hold keeps the finger velocity near zero before ACTION_UP, which
    avoids RecyclerView fling inertia and makes row-distance scrolling stable.
    """
    if swipe_pixels <= 0:
        return False
    left = int(list_bounds["left"])
    right = int(list_bounds["right"])
    top = int(list_bounds["top"])
    bottom = int(list_bounds["bottom"])
    if right - left < 8 or bottom - top < 8:
        logging.warning("scroll_engine 列表过小 lb=%s", list_bounds)
        return False

    coef = _DURATION_PX_COEF if duration_px_coef is None else float(duration_px_coef)
    min_ms = _MIN_DURATION_MS if min_duration_ms is None else int(min_duration_ms)

    start_x = (left + right) // 2
    start_y = bottom - bottom_padding
    floor_y = top + top_padding if end_floor_y is None else int(end_floor_y)
    end_y = max(floor_y, start_y - swipe_pixels)
    end_x = start_x

    actual_dy = start_y - end_y
    if actual_dy + 1 < swipe_pixels:
        logging.warning(
            "smooth_scroll_up 行程被裁剪 requested=%d actual=%d floor_y=%d start_y=%d list_top=%d",
            swipe_pixels,
            actual_dy,
            floor_y,
            start_y,
            top,
        )

    total_ms = max(min_ms, int(round(actual_dy * coef)))
    step_sleep = max(0.002, (total_ms / 1000.0) / max(1, steps))

    try:
        touch = dev_d.touch
        touch.down(start_x, start_y)
        for i in range(1, steps + 1):
            t = _ease_out_cubic(i / steps)
            y = int(round(start_y + (end_y - start_y) * t))
            touch.move(start_x, y)
            time.sleep(step_sleep)
        if end_hold_s > 0:
            try:
                touch.sleep(end_hold_s)
            except Exception:
                time.sleep(end_hold_s)
        touch.up(end_x, end_y)
        logging.debug(
            "smooth_scroll_up requested=%d actual_dy=%d steps=%d total_ms=%d hold=%.2fs floor_y=%d",
            swipe_pixels,
            actual_dy,
            steps,
            total_ms,
            end_hold_s,
            floor_y,
        )
        return True
    except Exception:
        logging.warning("smooth_scroll_up touch 链失败，回退 swipe", exc_info=True)
        try:
            dev_d.swipe(start_x, start_y, end_x, end_y, max(0.35, total_ms / 1000.0))
            time.sleep(end_hold_s)
            return True
        except Exception:
            logging.exception("smooth_scroll_up 最终回退仍失败")
            return False

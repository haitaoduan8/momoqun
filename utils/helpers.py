"""momoqun 通用工具函数。"""

import random
import re
import time
from typing import Optional, Tuple

BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(raw: str) -> Optional[Tuple[int, int, int, int]]:
    """解析 hierarchy 的 bounds 字符串，返回 (left, top, right, bottom) 或 None。"""
    m = BOUNDS_RE.fullmatch(raw or "")
    if not m:
        return None
    left, top, right, bottom = map(int, m.groups())
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def random_delay(settings: dict, key: str = "delay") -> None:
    """从 settings 读取 min/max 做随机延迟。"""
    try:
        d = settings.get(key) or {}
        lo = float(d.get("min", 0.3))
        hi = float(d.get("max", 1.0))
        if hi < lo:
            hi = lo
        time.sleep(random.uniform(lo, hi))
    except Exception:
        time.sleep(random.uniform(0.2, 0.5))


def sleep_jitter(base: float, jitter_ratio: float = 0.3) -> None:
    """以 base 为基础，加 ±jitter_ratio 随机抖动后 sleep。"""
    if base <= 0:
        return
    jitter = base * jitter_ratio
    time.sleep(max(0.0, base + random.uniform(-jitter, jitter)))

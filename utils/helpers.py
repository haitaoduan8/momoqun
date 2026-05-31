"""momoqun 通用工具函数。"""

import logging
import os
import random
import re
import time
from typing import Any, Dict, Optional, Tuple

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


# ---------------------------------------------------------------------------
# ElementsConfig — 元素配置统一读取（消除各模块重复的 _get_rid / _get_text）
# ---------------------------------------------------------------------------

class ElementsConfig:
    """对 elements.yaml 的统一访问层。

    替代各模块中重复的 ``_get_rid`` / ``_get_text`` 方法。
    """

    def __init__(self, elements: dict) -> None:
        self._data = elements or {}

    @property
    def raw(self) -> dict:
        return self._data

    def get_rid(self, *path: str) -> Optional[str]:
        """按路径读取 resourceId，如 ``get_rid("chat_list", "chat_row")``。"""
        node: Any = self._data
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("resourceId") or None
        return None

    def get_text(self, *path: str) -> Optional[str]:
        """按路径读取 text，如 ``get_text("entry_elements", "sayhi_entry")``。"""
        node: Any = self._data
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("text") or None
        return None

    def get_node(self, *path: str) -> Optional[dict]:
        """按路径读取整个节点 dict。"""
        node: Any = self._data
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node if isinstance(node, dict) else None


# ---------------------------------------------------------------------------
# 模板匹配（消除 u2_driver / agent_driver 重复）
# ---------------------------------------------------------------------------

def match_template_on_screen(
    screen_bgr: Any,
    template_path: str,
    template: Any,
    threshold: float = 0.8,
) -> Optional[Tuple[int, int]]:
    """在 screen_bgr (BGR ndarray) 上做模板匹配，返回匹配中心 (x, y) 或 None。"""
    import cv2

    th, tw = template.shape[:2]
    sh, sw = screen_bgr.shape[:2]
    if th > sh or tw > sw:
        logging.warning("模板尺寸大于屏幕: %s", template_path)
        return None
    res = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        logging.info(
            "未找到匹配模板(阈值 %.2f, 最高得分 %.3f): %s",
            threshold, max_val, template_path,
        )
        return None
    top_x, top_y = max_loc
    cx = top_x + tw // 2
    cy = top_y + th // 2
    logging.info(
        "模板匹配成功: %s 中心(%d,%d) 得分 %.3f",
        template_path, cx, cy, max_val,
    )
    return (cx, cy)


# ---------------------------------------------------------------------------
# 统一日志初始化（消除 main.py / app.py / server.py 重复配置）
# ---------------------------------------------------------------------------

def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    file_mode: str = "w",
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt: str = "%H:%M:%S",
) -> None:
    """统一配置 root logger。重复调用安全（不会叠加 handler）。"""
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)
    formatter = logging.Formatter(fmt, datefmt=datefmt)
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        fh = logging.FileHandler(log_file, mode=file_mode, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root.addHandler(sh)


# ---------------------------------------------------------------------------
# UI 页面导航（消除 greeter / chatter / group_inviter 重复的 go_back_to_chat_list）
# ---------------------------------------------------------------------------

def go_back_to_chat_list(
    driver: Any,
    elements: dict,
    *,
    max_backs: int = 5,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """从任意界面按 back 返回聊天列表。

    验证策略：同时检测 chat_row 存在 且 accept_button 不存在
    （区分主聊天列表和招呼子页面）。
    """
    log = logger or logging.getLogger("navigator")
    ec = ElementsConfig(elements)
    row_rid = ec.get_rid("chat_list", "chat_row")
    accept_rid = ec.get_rid("buttons", "accept_button")
    send_rid = ec.get_rid("buttons", "send_button")
    input_rid = ec.get_rid("buttons", "input_box")

    for i in range(max_backs):
        try:
            driver.d.press("back")
        except Exception:
            log.debug("back 按键异常", exc_info=True)
        time.sleep(random.uniform(0.5, 1.0))
        try:
            driver.wait_ui_stable(max_wait=1.0)
        except Exception:
            pass
        try:
            xml = driver.d.dump_hierarchy()
            if row_rid and row_rid in xml:
                # 在招呼子页面（有 accept_button）→ 继续 back
                if accept_rid and accept_rid in xml:
                    log.debug("仍在招呼子页面，继续 back")
                    continue
                # 在私聊页面（有 send_button/input_box）→ 继续 back
                if send_rid and send_rid in xml:
                    log.debug("仍在私聊页面，继续 back")
                    continue
                if input_rid and input_rid in xml:
                    log.debug("仍在私聊页面（input_box），继续 back")
                    continue
                log.info("已回到聊天列表 (第 %d 次 back)", i + 1)
                return True
        except Exception:
            log.debug("dump hierarchy 检测异常", exc_info=True)

    log.warning("%d 次 back 后仍未回到聊天列表", max_backs)
    return False

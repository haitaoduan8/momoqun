"""路线 C 的 APK Agent 驱动。

设计：
- ``AgentHandler``：实现 ``Driver`` Protocol，业务模块无需感知底层通道；
- ``AgentDeviceProxy``：实现 ``DeviceProxy`` Protocol，所有 RPC 转发给
  ``agent_router.AgentRouter`` 上挂着的对应 serial 的 WebSocket 连接。

通信约定见 ``docs/agent-protocol.md``。
"""

from __future__ import annotations

import base64
import io
import logging
import os
import random
import time
import xml.etree.ElementTree as ET
from typing import Any, Optional, Tuple

import cv2
import numpy as np
import yaml


_NOT_IMPL = "AgentDriver 该方法等待 Week 2 APK 实现后启用"
_DEFAULT_RPC_TIMEOUT = 15.0


class AgentDeviceProxy:
    """底层设备代理：所有调用 → ``AgentRouter.call_sync(serial, method, params)``。

    方法签名与 ``DeviceProxy`` Protocol 兼容，业务代码（``self.driver.d.xxx``）
    可以无感切换。
    """

    def __init__(self, serial: str, router: Optional[Any] = None,
                 rpc_timeout: float = _DEFAULT_RPC_TIMEOUT) -> None:
        self.serial = serial
        # 显式传入；若 None 则下次调用时从 agent_router.get_router() 兜底获取
        self._router = router
        self._rpc_timeout = rpc_timeout

    # ------------------------------------------------------------------
    # u2 Selector 兼容：d(resourceId=..., text=...) 返回 _UiObjectProxy
    # ------------------------------------------------------------------
    def __call__(self, **kwargs: Any) -> "_UiObjectProxy":
        """d(text=..., resourceId=...) 风格的 selector，返回可链式调用的代理对象。"""
        return _UiObjectProxy(self, **kwargs)

    def _r(self):
        if self._router is None:
            from agent_router import get_router
            self._router = get_router()
        return self._router

    def _call(self, method: str, params: Optional[dict] = None,
              timeout: Optional[float] = None) -> Any:
        return self._r().call_sync(
            self.serial, method, params or {}, timeout=timeout or self._rpc_timeout
        )

    # ------------------------------------------------------------------
    # DeviceProxy 接口
    # ------------------------------------------------------------------
    def dump_hierarchy(self, compressed: bool = False, pretty: bool = False) -> str:
        res = self._call("dump_hierarchy", {"compressed": bool(compressed)})
        if not isinstance(res, dict) or "xml" not in res:
            raise RuntimeError(f"agent dump_hierarchy 返回异常: {res!r}")
        return res["xml"]

    def click(self, x: int, y: int) -> None:
        self._call("click", {"x": int(x), "y": int(y)})

    def long_click(self, x: int, y: int, duration: float = 0.5) -> None:
        self._call(
            "long_click",
            {"x": int(x), "y": int(y), "duration_ms": int(duration * 1000)},
        )

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        self._call(
            "swipe",
            {
                "x1": int(x1), "y1": int(y1),
                "x2": int(x2), "y2": int(y2),
                "duration_ms": int(duration * 1000),
            },
        )

    def press(self, key: str) -> None:
        self._call("press_key", {"key": str(key)})

    def window_size(self) -> Tuple[int, int]:
        res = self._call("window_size", {})
        if not isinstance(res, dict) or "w" not in res or "h" not in res:
            raise RuntimeError(f"agent window_size 返回异常: {res!r}")
        return int(res["w"]), int(res["h"])

    def screenshot(self):
        """返回 PIL.Image.Image（与 u2 行为一致）。"""
        from PIL import Image

        res = self._call("screenshot", {"quality": 80}, timeout=self._rpc_timeout * 2)
        if not isinstance(res, dict) or "png_b64" not in res:
            raise RuntimeError(f"agent screenshot 返回异常: {type(res)}")
        png = base64.b64decode(res["png_b64"])
        return Image.open(io.BytesIO(png))

    def shell(self, cmd, timeout: float = 10):
        # AccessibilityService 路线下 master 进程无 adb 通道；业务在 agent 模式下避开。
        raise NotImplementedError("AgentDriver 不支持 adb shell")


# ---------------------------------------------------------------------------
# _UiObjectProxy — d(text=..., resourceId=...) 风格的 selector 代理
# ---------------------------------------------------------------------------


class _Bounds:
    """bounds 四元组薄封装。"""

    __slots__ = ("left", "top", "right", "bottom")

    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    @property
    def cx(self) -> int:
        return (self.left + self.right) // 2

    @property
    def cy(self) -> int:
        return (self.top + self.bottom) // 2


def _parse_bounds_attr(raw: str) -> Optional[_Bounds]:
    """从 ``bounds="[l,t][r,b]"`` 字符串提取 _Bounds。"""
    import re

    m = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", raw or "")
    if not m:
        return None
    l, t, r, b = map(int, m.groups())
    if r <= l or b <= t:
        return None
    return _Bounds(l, t, r, b)


def _node_matches(node: Any, **kwargs: Any) -> bool:
    """检查 XML node attrib 是否匹配所有 selector 条件。"""
    for key, value in kwargs.items():
        if key == "resourceId":
            if (node.attrib.get("resource-id") or "") != value:
                return False
        elif key == "text":
            if (node.attrib.get("text") or "").strip() != value:
                return False
        elif key == "textContains":
            if value not in (node.attrib.get("text") or ""):
                return False
        elif key == "className":
            if (node.attrib.get("class") or "") != value:
                return False
        elif key == "clickable":
            if node.attrib.get("clickable") != str(value).lower():
                return False
        # 其它 selector 按需扩展
    return True


def _find_all_matching(root: Any, **kwargs: Any) -> list:
    """返回所有匹配 selector 的 XML node 列表。"""
    matched = []
    for node in root.iter():
        if _node_matches(node, **kwargs):
            matched.append(node)
    return matched


class _UiObjectProxy:
    """Selector 代理，内部通过 dump_hierarchy + XML 解析实现。

    支持的链式调用:
      - ``.exists`` (property)
      - ``.wait(timeout=5)``
      - ``.click()``
      - ``.fling.toBeginning(max_swipes=10)``
      - ``.scroll.vert.forward(steps)``
      - ``.get_text()``
      - ``.info`` (property, 返回 dict)
    """

    def __init__(self, proxy: AgentDeviceProxy, **kwargs: Any) -> None:
        self._proxy = proxy
        self._selectors = kwargs
        self._fling = _FlingProxy(self)
        self._scroll = _ScrollProxy(self)

    # ---- internal helpers ----

    def _dump_and_find(self) -> Tuple[Optional[Any], Optional[_Bounds]]:
        """dump hierarchy，返回第一个匹配节点及其 bounds。"""
        try:
            xml = self._proxy.dump_hierarchy()
            root = ET.fromstring(xml)
            for node in root.iter():
                if _node_matches(node, **self._selectors):
                    b = _parse_bounds_attr(node.attrib.get("bounds", ""))
                    return node, b
        except Exception:
            logging.debug("_UiObjectProxy._dump_and_find 异常", exc_info=True)
        return None, None

    def _dump_and_find_all(self) -> list:
        """dump hierarchy，返回所有匹配节点的 (node, bounds) 列表。"""
        try:
            xml = self._proxy.dump_hierarchy()
            root = ET.fromstring(xml)
            results = []
            for node in root.iter():
                if _node_matches(node, **self._selectors):
                    b = _parse_bounds_attr(node.attrib.get("bounds", ""))
                    results.append((node, b))
            return results
        except Exception:
            logging.debug("_UiObjectProxy._dump_and_find_all 异常", exc_info=True)
        return []

    # ---- public API ----

    @property
    def exists(self) -> bool:
        node, _ = self._dump_and_find()
        return node is not None

    def wait(self, timeout: float = 5.0) -> bool:
        deadline = time.time() + max(0.5, float(timeout))
        while time.time() < deadline:
            node, _ = self._dump_and_find()
            if node is not None:
                return True
            time.sleep(0.2)
        return False

    def click(self) -> bool:
        _, b = self._dump_and_find()
        if b is None:
            return False
        self._proxy.click(b.cx, b.cy)
        return True

    def get_text(self) -> str:
        node, _ = self._dump_and_find()
        if node is None:
            return ""
        return (node.attrib.get("text") or "").strip()

    @property
    def info(self) -> dict:
        node, b = self._dump_and_find()
        if node is None:
            return {}
        result = dict(node.attrib)
        if b:
            result["bounds"] = {
                "left": b.left, "top": b.top,
                "right": b.right, "bottom": b.bottom,
            }
        return result

    @property
    def fling(self) -> "_FlingProxy":
        return self._fling

    @property
    def scroll(self) -> "_ScrollProxy":
        return self._scroll


class _FlingProxy:
    """模拟 u2 UiObject.fling。"""

    def __init__(self, ui_obj: _UiObjectProxy) -> None:
        self._ui = ui_obj

    def _bounds(self) -> Optional[_Bounds]:
        _, b = self._ui._dump_and_find()
        return b

    def toBeginning(self, max_swipes: int = 10) -> None:
        b = self._bounds()
        if b is None:
            return
        cx = b.cx
        y_bottom = b.bottom - 40
        y_top = b.top + 40
        for _ in range(max(1, max_swipes)):
            try:
                self._ui._proxy.swipe(cx, y_bottom, cx, y_top, 0.3)
            except Exception:
                break
            time.sleep(0.25)

    def toEnd(self, max_swipes: int = 10) -> None:
        b = self._bounds()
        if b is None:
            return
        cx = b.cx
        y_top = b.top + 40
        y_bottom = b.bottom - 40
        for _ in range(max(1, max_swipes)):
            try:
                self._ui._proxy.swipe(cx, y_top, cx, y_bottom, 0.3)
            except Exception:
                break
            time.sleep(0.25)


class _ScrollProxy:
    """模拟 u2 UiObject.scroll。"""

    def __init__(self, ui_obj: _UiObjectProxy) -> None:
        self.vert = _VertScrollProxy(ui_obj)


class _VertScrollProxy:
    """模拟 u2 UiObject.scroll.vert。"""

    def __init__(self, ui_obj: _UiObjectProxy) -> None:
        self._ui = ui_obj

    def forward(self, steps: int = 50) -> None:
        _, b = self._ui._dump_and_find()
        if b is None:
            return
        cx = b.cx
        y_from = b.bottom - 40
        y_to = b.top + 40
        try:
            self._ui._proxy.swipe(cx, y_from, cx, y_to, 0.3)
        except Exception:
            logging.debug("_VertScrollProxy.forward swipe 异常", exc_info=True)

    def backward(self, steps: int = 50) -> None:
        _, b = self._ui._dump_and_find()
        if b is None:
            return
        cx = b.cx
        y_from = b.top + 40
        y_to = b.bottom - 40
        try:
            self._ui._proxy.swipe(cx, y_from, cx, y_to, 0.3)
        except Exception:
            logging.debug("_VertScrollProxy.backward swipe 异常", exc_info=True)

class AgentHandler:
    """路线 C 高层驱动，实现 ``Driver`` Protocol。"""

    def __init__(
        self,
        config_path: str = "config/settings.yaml",
        serial: Optional[str] = None,
        router: Optional[Any] = None,
    ) -> None:
        with open(config_path, "r", encoding="utf-8") as f:
            self.settings = yaml.safe_load(f)["config"]
        self.serial = serial or ""
        self.d: AgentDeviceProxy = AgentDeviceProxy(self.serial, router=router)
        self._ime_ready: Optional[bool] = None
        logging.info("AgentHandler 初始化 serial=%s router=%s", self.serial, router)

    # ------------------------------------------------------------------
    # IME 管理（agent 路线下走 IME APK）
    # ------------------------------------------------------------------
    def ensure_input_ime_ready(self, timeout: float = 8.0) -> bool:
        """检查 agent 端 IME 是否被选为默认。

        agent 内部走 ``ime_status`` RPC：
          {"selected": bool, "available": bool}
        若 agent 未选用，提示用户在系统设置里启用 momoqun-agent-ime。
        """
        if self._ime_ready is True:
            return True
        try:
            res = self.d._call("ime_status", {}, timeout=timeout)
        except Exception:
            logging.exception("agent ime_status RPC 异常")
            self._ime_ready = False
            return False
        if not isinstance(res, dict):
            self._ime_ready = False
            return False
        if not res.get("available"):
            logging.error(
                "agent[%s] momoqun-ime 未安装；请重新装 agent APK",
                self.serial,
            )
            self._ime_ready = False
            return False
        if not res.get("selected"):
            logging.warning(
                "agent[%s] momoqun-ime 未被设为默认；请在系统设置 → 语言与输入法里选用",
                self.serial,
            )
            self._ime_ready = False
            return False
        self._ime_ready = True
        return True

    def invalidate_input_ime_cache(self) -> None:
        self._ime_ready = None

    # ------------------------------------------------------------------
    # 高层动作（与 DeviceHandler 同签名）
    # ------------------------------------------------------------------
    def _click_point_with_offset(self, x: int, y: int, skip_delay: bool = False) -> None:
        offset_x = random.randint(
            -self.settings["click_offset"]["x"], self.settings["click_offset"]["x"]
        )
        offset_y = random.randint(
            -self.settings["click_offset"]["y"], self.settings["click_offset"]["y"]
        )
        self.d.click(x + offset_x, y + offset_y)
        if not skip_delay:
            time.sleep(
                random.uniform(self.settings["delay"]["min"], self.settings["delay"]["max"])
            )

    def random_click_xy(self, x: int, y: int, skip_delay: bool = False) -> None:
        self._click_point_with_offset(x, y, skip_delay=skip_delay)

    def random_click(self, selector: str, skip_delay: bool = False) -> bool:
        """通过 resourceId 或 text 在 hierarchy 中查找元素并点击其中心。"""
        try:
            xml = self.d.dump_hierarchy()
            root = ET.fromstring(xml)
            for node in root.iter():
                rid = node.attrib.get("resource-id") or ""
                txt = (node.attrib.get("text") or "").strip()
                if rid == selector or txt == selector:
                    b = _parse_bounds_attr(node.attrib.get("bounds", ""))
                    if b:
                        self._click_point_with_offset(b.cx, b.cy, skip_delay=skip_delay)
                        return True
            return False
        except Exception:
            logging.exception("AgentHandler.random_click 异常 selector=%s", selector)
            return False

    def click_uielement(self, el, skip_delay: bool = False) -> bool:
        """点击 _UiObjectProxy 或任何带 bounds 信息的对象。"""
        try:
            if isinstance(el, _UiObjectProxy):
                _, b = el._dump_and_find()
                if b:
                    self._click_point_with_offset(b.cx, b.cy, skip_delay=skip_delay)
                    return True
                return False
            # 兼容：el 是一个 dict 形式的 bounds
            if isinstance(el, dict):
                cx = (el.get("left", 0) + el.get("right", 0)) // 2
                cy = (el.get("top", 0) + el.get("bottom", 0)) // 2
                self._click_point_with_offset(cx, cy, skip_delay=skip_delay)
                return True
            logging.warning("click_uielement: 不支持的 el 类型 %s", type(el))
            return False
        except Exception:
            logging.exception("AgentHandler.click_uielement 异常")
            return False

    def is_keyboard_shown(self, input_box_rid: Optional[str] = None) -> bool:
        try:
            res = self.d._call("keyboard_visible", {})
        except Exception:
            return False
        return bool(res and res.get("visible"))

    def swipe_scroll_down(self, duration: float = 0.35) -> None:
        w, h = self.d.window_size()
        x = int(w * 0.5) + random.randint(
            -self.settings["click_offset"]["x"], self.settings["click_offset"]["x"]
        )
        y1 = int(h * 0.72)
        y2 = int(h * 0.32)
        self.d.swipe(x, y1, x, y2, duration)
        time.sleep(
            random.uniform(self.settings["delay"]["min"], self.settings["delay"]["max"])
        )

    def swipe_half_screen_up(self, duration: float = 0.35) -> None:
        """手指上滑约半屏，用于露出底部被遮挡的控件（如群信息页邀请 + 号）。"""
        try:
            w, h = self.d.window_size()
            x = int(w * 0.5) + random.randint(
                -self.settings["click_offset"]["x"], self.settings["click_offset"]["x"]
            )
            y1 = int(h * 0.75)
            y2 = int(h * 0.25)
            self.d.swipe(x, y1, x, y2, duration)
            time.sleep(
                random.uniform(self.settings["delay"]["min"], self.settings["delay"]["max"])
            )
        except Exception:
            logging.exception("AgentHandler.swipe_half_screen_up 异常")

    def wait_ui_stable(self, max_wait: float = 1.2, poll: float = 0.12) -> bool:
        # 连续两次 dump_hierarchy 的 hash 一致即视为稳定。
        import hashlib

        deadline = time.time() + max_wait
        last: Optional[str] = None
        while time.time() < deadline:
            try:
                xml = self.d.dump_hierarchy()
            except Exception:
                logging.debug("agent wait_ui_stable: dump_hierarchy 异常", exc_info=True)
                time.sleep(poll)
                continue
            h = hashlib.md5(xml.encode("utf-8")).hexdigest()
            if h == last:
                return True
            last = h
            time.sleep(poll)
        return False

    # ------------------------------------------------------------------
    # 模板匹配：本地 OpenCV + agent 截图
    # ------------------------------------------------------------------
    def capture_screen_bgr(self):
        pil_im = self.d.screenshot()
        return cv2.cvtColor(np.asarray(pil_im), cv2.COLOR_RGB2BGR)

    def find_image(self, template_path: str, threshold: float = 0.8):
        try:
            if not os.path.isfile(template_path):
                logging.error("模板文件不存在: %s", template_path)
                return None
            screen = self.capture_screen_bgr()
            template = cv2.imread(template_path)
            if template is None:
                logging.error("模板图无法读取: %s", template_path)
                return None
            return _match_template_on_screen(screen, template_path, template, threshold)
        except Exception:
            logging.exception("agent find_image 执行异常: %s", template_path)
            return None

    def click_image(self, template_path: str, threshold: float = 0.8) -> bool:
        pos = self.find_image(template_path, threshold=threshold)
        if pos is None:
            return False
        self._click_point_with_offset(pos[0], pos[1])
        return True

    # ------------------------------------------------------------------
    # 文本输入（IME APK 走 RPC）
    # ------------------------------------------------------------------
    def human_type(self, text: str, chunk_size: int = 3) -> None:
        if not text:
            return
        if not self.ensure_input_ime_ready():
            raise RuntimeError(
                "agent momoqun-ime 未就绪，已拒绝 type_text 以避免软键盘点击回退"
            )
        # 按 chunk 切分以模拟真人输入节奏
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            if not chunk:
                continue
            self.d._call("type_text", {"text": chunk})
            time.sleep(random.uniform(0.1, 0.3))


# ---------------------------------------------------------------------------
# 公共工具：委托给 utils.helpers 的共享实现
# ---------------------------------------------------------------------------
def _match_template_on_screen(screen_bgr, template_path: str, template, threshold: float):
    from utils.helpers import match_template_on_screen
    return match_template_on_screen(screen_bgr, template_path, template, threshold)

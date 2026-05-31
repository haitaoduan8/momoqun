"""路线 C 的 APK Agent 驱动 — Week 1 Day 3 stub。

设计：
- ``AgentHandler``：与 ``u2_driver.DeviceHandler`` 同签名，业务模块无需感知；
- ``AgentDeviceProxy``：实现 ``DeviceProxy`` Protocol，所有 RPC 转发给
  ``agent_router.AgentRouter`` 上挂着的对应 serial 的 WebSocket 连接；
- 当前文件只搭骨架，方法体在 Day 4-5 与 agent_router.py 一起补全。

通信约定见 ``docs/agent-protocol.md``（Day 5 定稿）。
"""

from __future__ import annotations

import base64
import io
import logging
import os
import random
import time
from typing import Any, Optional, Tuple

import cv2
import numpy as np
import yaml


_NOT_IMPL = "AgentDriver 该方法等待 Week 2 APK 实现后启用"
_DEFAULT_RPC_TIMEOUT = 15.0


class AgentDeviceProxy:
    """底层设备代理：所有调用 → ``AgentRouter.call_sync(serial, method, params)``。

    方法签名与 ``uiautomator2.Device`` 鸭子兼容，业务代码（``self.driver.d.xxx``）
    可以无感切换。
    """

    def __init__(self, serial: str, router: Optional[Any] = None,
                 rpc_timeout: float = _DEFAULT_RPC_TIMEOUT) -> None:
        self.serial = serial
        # 显式传入；若 None 则下次调用时从 agent_router.get_router() 兜底获取
        self._router = router
        self._rpc_timeout = rpc_timeout

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


class AgentHandler:
    """与 ``u2_driver.DeviceHandler`` 同签名的高层驱动。"""

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
        # agent 模式没有 u2 Selector；业务应改用 random_click_xy（坐标已由 hierarchy 解析得到）。
        raise NotImplementedError("AgentDriver 不支持 selector 风格点击，请用 random_click_xy")

    def click_uielement(self, el, skip_delay: bool = False) -> bool:
        raise NotImplementedError("AgentDriver 不支持 UiObject，请用 random_click_xy")

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

    def wait_ui_stable(self, max_wait: float = 1.2, poll: float = 0.12) -> bool:
        # 与 u2_driver 一致：连续两次 dump_hierarchy 的 hash 一致即视为稳定。
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

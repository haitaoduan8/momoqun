"""Driver / DeviceProxy 协议定义。

业务模块对设备的依赖收敛到这两个 Protocol：

- 高频调用：``driver.d.dump_hierarchy() / click / swipe / press / window_size``
  → 走 ``DeviceProxy``。
- 高层动作 + 配置：``driver.random_click / human_type / find_image / ensure_input_ime_ready``
  → 走 ``Driver``。

任何新实现（uiautomator2 / agent-apk / 模拟器自带 API）只要鸭子类型兼容即可。
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class DeviceProxy(Protocol):
    """底层设备代理（对应 ``uiautomator2.Device`` 的最小子集）。

    所有方法均为同步阻塞，调用方负责异常处理。
    """

    def dump_hierarchy(self, compressed: bool = False, pretty: bool = False) -> str: ...

    def click(self, x: int, y: int) -> None: ...

    def long_click(self, x: int, y: int, duration: float = 0.5) -> None: ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None: ...

    def press(self, key: str) -> None:  # back / home / enter / recent / ...
        ...

    def window_size(self) -> Tuple[int, int]: ...

    def screenshot(self) -> "object":  # PIL.Image 或类似可序列化对象
        ...

    def shell(self, cmd, timeout: float = 10):  # → uiautomator2.ShellResponse
        ...


@runtime_checkable
class Driver(Protocol):
    """高层驱动：包含 settings、底层 device proxy 与高层动作。"""

    settings: dict
    d: DeviceProxy  # 底层设备代理

    # IME 管理（高层动作；agent 实现可走 IME APK，u2 实现走 ADB Keyboard）
    def ensure_input_ime_ready(self, timeout: float = 8.0) -> bool: ...

    def invalidate_input_ime_cache(self) -> None: ...

    # 高层动作
    def random_click_xy(self, x: int, y: int, skip_delay: bool = False) -> None: ...

    def random_click(self, selector: str, skip_delay: bool = False) -> bool: ...

    def human_type(self, text: str, chunk_size: int = 3) -> None: ...

    def swipe_scroll_down(self, duration: float = 0.35) -> None: ...

    def wait_ui_stable(self, max_wait: float = 1.2, poll: float = 0.12) -> bool: ...

    # 图像匹配（可选；agent driver 通过 screenshot RPC + 本地 OpenCV 实现）
    def find_image(self, template_path: str, threshold: float = 0.8): ...

    def click_image(self, template_path: str, threshold: float = 0.8) -> bool: ...

    def is_keyboard_shown(self, input_box_rid: Optional[str] = None) -> bool: ...

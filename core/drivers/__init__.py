"""Driver 抽象层。

`base.Driver`：高层驱动接口（连接管理 + IME 就绪 + 模板匹配 + 高层动作）。
`base.DeviceProxy`：底层设备代理（dump_hierarchy / click / swipe / press / …）。

实现：
- `u2_driver.DeviceHandler`  — 现有 uiautomator2 实现（默认走 ADB 通道）
- `agent_driver.AgentHandler` — 路线 C 的 APK Agent 实现（WebSocket → AccessibilityService）
"""

from core.drivers.base import Driver, DeviceProxy  # noqa: F401

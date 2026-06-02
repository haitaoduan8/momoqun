"""Driver 抽象层。

`base.Driver`：高层驱动接口（连接管理 + IME 就绪 + 模板匹配 + 高层动作）。
`base.DeviceProxy`：底层设备代理（dump_hierarchy / click / swipe / press / …）。

唯一实现：`agent_driver.AgentHandler`（路线 C — APK Agent，WebSocket 通道）。
"""

from core.drivers.base import Driver, DeviceProxy  # noqa: F401

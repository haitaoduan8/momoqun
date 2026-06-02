"""向后兼容 shim：``from core.driver import DeviceHandler`` 仍然可用。

路线 C 唯一通路：AgentHandler。
"""

from core.drivers.agent_driver import AgentHandler as DeviceHandler  # noqa: F401

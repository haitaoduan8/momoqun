"""向后兼容 shim：``from core.driver import DeviceHandler`` 仍然可用。

新代码请直接 ``from core.drivers.u2_driver import DeviceHandler`` 或
``from core.drivers import Driver, DeviceProxy``。
"""

from core.drivers.u2_driver import DeviceHandler  # noqa: F401

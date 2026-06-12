"""测试：从陌陌聊天列表 → 退回微霸 → 换号推送文件 → 上号

通过 server API + 直接 RPC 调用完成。
"""

import sys
import os
import logging
import time
import asyncio
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import setup_logging
from utils.config_load import load_settings, load_elements
from core.weiba_refresh import ensure_weiba_phone_and_refresh
from core.account_boot import run_account_boot_from_phone, BootResult
from ops.account_swap import swap_account_file_for_device
from agent_router import get_router

SERIAL = "af75a260"
LOCAL_DIR = "/Users/duanhaitao/Desktop/未命名文件夹"
REMOTE_DIR = "/sdcard/Download"


def _start_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main():
    setup_logging(log_file=os.path.expanduser("~/Desktop/test_swap_boot.log"), file_mode="w")
    log = logging.getLogger("test_swap_boot")

    settings = load_settings()
    elements = load_elements()

    log.info("=" * 60)
    log.info("开始测试：聊天列表 → 微霸 → 换号 → 上号")
    log.info("=" * 60)

    # 启动独立 event loop 线程供 AgentRouter 使用
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=_start_event_loop, args=(loop,), daemon=True)
    t.start()

    router = get_router()
    router.bind_loop(loop)

    # 等待 Agent 连接
    log.info("[0/4] 等待 Agent 连接...")
    for _ in range(30):
        if router.get(SERIAL) is not None:
            break
        time.sleep(1)
    else:
        log.error("Agent %s 未在 30 秒内连接", SERIAL)
        loop.call_soon_threadsafe(loop.stop)
        return False

    log.info("Agent %s 已连接", SERIAL)

    # 1) 创建 AgentHandler
    log.info("[1/4] 初始化 AgentHandler...")
    from core.drivers.agent_driver import AgentHandler
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "settings.yaml"
    )
    driver = AgentHandler(config_path=config_path, serial=SERIAL)
    driver.ensure_input_ime_ready()
    log.info("AgentHandler 初始化完成")

    # 2) 从陌陌退回微霸手机界面 + 点刷新
    log.info("[2/4] 退回微霸手机界面并刷新...")
    ok = ensure_weiba_phone_and_refresh(driver, elements, settings, logger=log)
    if not ok:
        log.error("退回微霸失败，终止测试")
        loop.call_soon_threadsafe(loop.stop)
        return False
    log.info("微霸刷新完成 ✓")

    # 3) 换号：清空远程目录 + 推送新 .wbmomo 文件
    log.info("[3/4] 换号：推送新文件到设备...")
    result = swap_account_file_for_device(
        adb_serial=SERIAL,
        local_dir=LOCAL_DIR,
        remote_dir=REMOTE_DIR,
        agent_serial=SERIAL,
    )
    if not result.get("ok"):
        log.error("换号失败: %s", result.get("error"))
        loop.call_soon_threadsafe(loop.stop)
        return False
    log.info("换号成功 ✓ 推送文件: %s → %s", result.get("file"), result.get("remote"))

    # 4) 上号：微霸分身切换 → 打开陌陌
    log.info("[4/4] 开始上号（分身切换 → 打开陌陌）...")
    boot_result = run_account_boot_from_phone(driver, elements, settings, logger=log)
    if boot_result == BootResult.SUCCESS:
        log.info("上号完成 ✓")
    else:
        log.error("上号结果: %s", boot_result)
        loop.call_soon_threadsafe(loop.stop)
        return False

    log.info("=" * 60)
    log.info("全部流程完成！✓✓✓")
    log.info("=" * 60)
    loop.call_soon_threadsafe(loop.stop)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

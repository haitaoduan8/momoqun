"""momoqun — 陌陌群聊邀请自动化。

单机模式：直连一台设备，跑完整流水线。
多机模式：用 server.py + worker.py（推荐）。

用法：
    python3 main.py                          # 自动检测设备
    python3 main.py --serial af75a260        # 指定设备
    python3 main.py --serial 127.0.0.1:5555  # 连模拟器
    python3 main.py --keep-state             # 保留 friends/state 与日志（默认每次清空）
"""

import argparse
import logging
import os
import signal
import sys
import time

import uiautomator2 as u2
import yaml

from device_manager import DeviceThread
from data.storage import StorageHandler
from utils.helpers import setup_logging


def load_config() -> tuple:
    """加载 settings 和 elements 配置。"""
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
        settings = raw.get("config") or {}

    with open("config/elements.yaml", "r", encoding="utf-8") as f:
        elements = yaml.safe_load(f) or {}

    return settings, elements


def main() -> None:
    """单机模式入口：复用 DeviceThread 的主循环。"""
    parser = argparse.ArgumentParser(description="momoqun 单机模式")
    parser.add_argument("--serial", help="设备序列号（可选，不传则自动检测）")
    parser.add_argument(
        "--keep-state",
        action="store_true",
        help="保留 friends/<serial>.json 与运行日志（默认每次启动清空）",
    )
    args = parser.parse_args()

    # 日志初始化
    _log_file = os.path.expanduser("~/Desktop/momoqun.log")
    _file_mode = "a" if args.keep_state else "w"
    setup_logging(log_file=_log_file, file_mode=_file_mode)
    logger = logging.getLogger("momoqun")
    logger.info("日志文件: %s (mode=%s)", _log_file, _file_mode)

    # 加载配置
    try:
        settings, elements = load_config()
    except Exception:
        logging.exception("加载配置失败")
        sys.exit(1)

    # 解析 serial（自动检测时从 u2 拿 serial）
    resolved_serial = args.serial
    if not resolved_serial:
        try:
            d_tmp = u2.connect()
            resolved_serial = (d_tmp.info or {}).get("serial") or getattr(d_tmp, "serial", None)
        except Exception:
            resolved_serial = None
        logger.info("自动检测设备: %s", resolved_serial or "(unknown)")
    else:
        logger.info("指定设备: %s", resolved_serial)

    # per-device storage
    storage = StorageHandler.for_serial(resolved_serial)
    logger.info("好友库路径: %s", storage.file_path)

    # 启动前归档+清零
    if not args.keep_state:
        archived = storage.archive_and_clear()
        if archived:
            logger.info("已归档并清零好友库: %s", archived)
        else:
            logger.info("好友库已为空（无需备份）")
    else:
        logger.info("--keep-state 已指定，保留 friends/state 与日志")

    # 用 DeviceThread 复用多机模式的完整主循环
    dt = DeviceThread(
        serial=resolved_serial or "default",
        name="单机",
        settings=settings,
        elements=elements,
    )

    # 信号处理
    def handle_stop(sig, frame):
        logger.info("收到信号 %s，正在退出...", sig)
        dt.stop()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    logger.info("=" * 50)
    logger.info("momoqun 启动")
    logger.info("请确保手机在陌陌「消息」Tab（聊天列表页）")
    logger.info("轮次等待: %.1f 秒", float(settings.get("round_end_wait_s", 10)))
    logger.info("聊天轮数(点关注前): %d", settings.get("chat_rounds_before_follow", 3))
    logger.info("最大聊天轮数: %d", settings.get("max_chat_rounds", 10))
    logger.info("目标群聊: %s", settings.get("group_name", "未设置"))
    logger.info("=" * 50)

    # 启动设备线程
    dt.start()

    # 等待线程结束
    try:
        while dt.state == "running":
            time.sleep(1)
    except KeyboardInterrupt:
        dt.stop()

    # 安全退出归档
    try:
        archived = storage.archive_and_clear()
        if archived:
            logger.info("退出归档完成: %s", archived)
    except Exception:
        logger.exception("退出归档失败（忽略）")
    try:
        from core.message_pool import archive_and_clear_all_state
        archive_and_clear_all_state()
    except Exception:
        logger.exception("退出归档 state 失败（忽略）")
    logger.info("momoqun 已退出")


if __name__ == "__main__":
    main()

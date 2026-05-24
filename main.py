"""momoqun — 陌陌群聊邀请自动化。

单机模式：直连一台设备，跑完整流水线。
多机模式：用 server.py + worker.py（推荐）。

用法：
    python3 main.py                          # 自动检测设备
    python3 main.py --serial af75a260        # 指定设备
    python3 main.py --serial 127.0.0.1:5555  # 连模拟器
"""

import argparse
import logging
import signal
import sys
import time

import uiautomator2 as u2
import yaml

from core.driver import DeviceHandler
from core.pipeline import SessionRound
from data.storage import StorageHandler


def load_config() -> tuple:
    """加载 settings 和 elements 配置。"""
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
        settings = raw.get("config") or {}

    with open("config/elements.yaml", "r", encoding="utf-8") as f:
        elements = yaml.safe_load(f) or {}

    return settings, elements


def main() -> None:
    """主循环：while running → execute_one_round() → sleep(round_end_wait_s)。"""
    parser = argparse.ArgumentParser(description="momoqun 单机模式")
    parser.add_argument("--serial", help="设备序列号（可选，不传则自动检测）")
    args = parser.parse_args()

    # 日志
    import os as _os
    _log_dir = _os.path.expanduser("~/Desktop")
    _log_file = _os.path.join(_log_dir, "momoqun.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(_log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger("momoqun")
    logger.info("日志文件: %s", _log_file)

    # 加载配置
    try:
        settings, elements = load_config()
    except Exception:
        logging.exception("加载配置失败")
        sys.exit(1)

    # 连接设备
    storage = StorageHandler("data/friends.json")
    try:
        if args.serial:
            d = u2.connect(args.serial)
            logger.info("连接设备: %s", args.serial)
        else:
            d = u2.connect()
            logger.info("自动检测设备")
        driver = DeviceHandler("config/settings.yaml")
        driver.d = d
    except Exception:
        logging.exception("连接设备失败，请确认手机已通过 USB 连接或 ADB connect")
        sys.exit(1)

    # IME 就绪检查
    try:
        driver.ensure_input_ime_ready()
    except Exception:
        logger.warning("ADB Keyboard 检查异常（可能不影响运行）")

    # 创建 SessionRound（内部已包含 Greeter / Chatter / Inviter / MessagePool）
    session = SessionRound(driver, elements, settings, storage)

    round_end_wait = session.round_end_wait

    logger.info("=" * 50)
    logger.info("momoqun 启动")
    logger.info("请确保手机在陌陌「消息」Tab（聊天列表页）")
    logger.info("轮次等待: %.1f 秒", round_end_wait)
    logger.info("聊天轮数(点关注前): %d", settings.get("chat_rounds_before_follow", 3))
    logger.info("最大聊天轮数: %d", settings.get("max_chat_rounds", 10))
    logger.info("目标群聊: %s", settings.get("group_name", "未设置"))
    logger.info("=" * 50)

    running = True

    def handle_stop(sig, frame):
        nonlocal running
        logger.info("收到信号 %s，正在退出...", sig)
        running = False

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    consecutive_errors = 0
    max_errors = int(settings.get("max_consecutive_errors", 5))

    try:
        while running:
            try:
                # SessionRound.execute_one_round() 一次性执行四个阶段，
                # Phase 4 内部已 sleep round_end_wait_s 秒
                session.execute_one_round()
                consecutive_errors = 0

                logger.info(
                    "第 %d 轮完成 | 好友总数 %d | 本轮处理 %d",
                    session.round_number,
                    len(storage.get_all_friends()),
                    session.friends_processed_this_round,
                )

            except Exception:
                logging.exception("轮次异常")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    logger.error(
                        "连续异常 %d 次（>=%d），自动退出",
                        consecutive_errors,
                        max_errors,
                    )
                    running = False

            # 轮次间短暂让渡（主等待已在 _phase4_wait 内完成）
            time.sleep(0.5)

    except Exception:
        logging.exception("主循环异常")
    finally:
        logger.info("momoqun 已退出")


if __name__ == "__main__":
    main()

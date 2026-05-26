"""一对一多轮聊天：进入对话框、发送消息、等待回复。"""

import logging
import random
import time
import xml.etree.ElementTree as ET
from typing import Optional

from core.driver import DeviceHandler
from core.message_pool import MessagePoolManager
from data.storage import StorageHandler
from utils.helpers import parse_bounds, random_delay


class OneOnOneChatter:
    """与指定好友的一对一聊天管理器。"""

    def __init__(
        self,
        driver: DeviceHandler,
        elements: dict,
        settings: dict,
        storage: StorageHandler,
    ) -> None:
        self.driver = driver
        self.elements = elements
        self.settings = settings
        self.storage = storage
        self._logger = logging.getLogger("chatter")
        try:
            self._pool = MessagePoolManager(settings, state_path="data/state.json")
        except Exception:
            logging.exception("Chatter 消息池初始化失败，将无法获取消息")
            self._pool = None

    # ------------------------ 元素配置读取 ------------------------
    def _get_rid(self, *path: str) -> Optional[str]:
        node: any = self.elements
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("resourceId") or None
        return None

    def _get_text(self, *path: str) -> Optional[str]:
        node: any = self.elements
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("text") or None
        return None

    # ------------------------ 核心方法 ------------------------
    def find_and_enter_chat(self, name_or_uid: str) -> bool:
        """在聊天列表中找到指定好友并点击进入对话框。

        支持向下滚动翻找（最多 10 次）。
        """
        try:
            row_rid = self._get_rid("chat_list", "chat_row")
            name_rid = self._get_rid("chat_list", "chat_row_name")
            ignore_names = set(self.settings.get("chat_ignore_names") or [])

            if not row_rid:
                self._logger.warning("未配置 chat_row resourceId")
                return False

            for scroll_attempt in range(10):
                try:
                    xml = self.driver.d.dump_hierarchy()
                except Exception:
                    self._logger.debug("dump hierarchy 异常 scroll=%d", scroll_attempt)
                    time.sleep(0.5)
                    continue

                root = ET.fromstring(xml)
                for node in root.iter():
                    if node.attrib.get("resource-id") != row_rid:
                        continue

                    # 找到 chat_row 内的昵称
                    row_name = None
                    for child in node.iter():
                        if child.attrib.get("resource-id") == name_rid:
                            row_name = (child.attrib.get("text") or "").strip()
                            break

                    if not row_name:
                        continue

                    # 忽略系统消息
                    if row_name in ignore_names:
                        continue

                    # 模糊匹配
                    if name_or_uid and name_or_uid in row_name:
                        self._logger.info(
                            "找到好友: %s (scroll=%d)", row_name, scroll_attempt
                        )
                        b = parse_bounds(node.attrib.get("bounds", ""))
                        if b:
                            cx = (b[0] + b[2]) // 2
                            cy = (b[1] + b[3]) // 2
                            self.driver.random_click_xy(cx, cy)
                            random_delay(self.settings)
                            return True

                # 没找到，滚动继续
                self._logger.debug(
                    "当前屏未找到 %s，下翻 (scroll=%d)", name_or_uid, scroll_attempt
                )
                try:
                    self.driver.swipe_scroll_down()
                except Exception:
                    self._logger.debug("滚动异常", exc_info=True)
                time.sleep(random.uniform(0.3, 0.6))

            self._logger.warning("未在聊天列表中找到 %s（已翻 10 屏）", name_or_uid)
            return False
        except Exception:
            logging.exception("find_and_enter_chat 异常")
            return False

    def send_message(self, text: str) -> bool:
        """在当前对话框中发送一条消息。

        流程：点输入框 → human_type 输入 → 点发送按钮。
        """
        if not text:
            return False
        try:
            input_rid = self._get_rid("buttons", "input_box")
            send_rid = self._get_rid("buttons", "send_button")

            if not input_rid or not send_rid:
                self._logger.warning("未配置输入框或发送按钮")
                return False

            # 点输入框
            el_input = self.driver.d(resourceId=input_rid)
            if not el_input.exists:
                self._logger.warning("输入框不存在")
                return False
            self.driver.click_uielement(el_input)
            random_delay(self.settings)

            # 输入消息
            self.driver.human_type(text)
            random_delay(self.settings)

            # 点发送
            el_send = self.driver.d(resourceId=send_rid)
            if el_send.exists:
                self.driver.click_uielement(el_send)
                self._logger.info("消息已发送: %s", text[:30])
                return True

            self._logger.warning("发送按钮不存在")
            return False
        except Exception:
            logging.exception("send_message 异常")
            return False

    def wait_for_peer_reply(self, timeout_s: float = 30,
                            friend_name: str = None) -> bool:
        """回到聊天列表，等目标好友回复。

        friend_name 不为空时，只检测该好友的未读角标；
        为空时检测任意未读（兼容旧调用）。
        """
        deadline = time.time() + timeout_s
        try:
            # 先回到聊天列表
            try:
                self.driver.d.press("back")
            except Exception:
                self._logger.debug("back 异常", exc_info=True)
            time.sleep(random.uniform(0.5, 1.0))

            while time.time() < deadline:
                try:
                    xml = self.driver.d.dump_hierarchy()
                except Exception:
                    self._logger.debug("wait 中 dump hierarchy 异常")
                    time.sleep(2)
                    continue

                row_rid = self._get_rid("chat_list", "chat_row")
                name_rid = self._get_rid("chat_list", "chat_row_name")
                unread_rid = self._get_rid("chat_list", "chat_unread_badge")
                root = ET.fromstring(xml) if xml else None

                if root is None or not row_rid:
                    time.sleep(random.uniform(2.0, 3.5))
                    continue

                for node in root.iter():
                    if node.attrib.get("resource-id") != row_rid:
                        continue

                    # 找行内名字和未读角标
                    row_name = ""
                    has_badge = False
                    for child in node.iter():
                        rid = child.attrib.get("resource-id", "")
                        if rid == unread_rid:
                            has_badge = True
                        elif rid == name_rid:
                            row_name = (child.attrib.get("text") or "").strip()

                    if not has_badge:
                        continue

                    # 如果指定了目标好友，必须匹配
                    if friend_name and friend_name not in row_name:
                        continue

                    self._logger.info(
                        "检测到目标好友回复: %s", row_name
                    )
                    return True

                time.sleep(random.uniform(2.0, 3.5))

            self._logger.info("wait_for_peer_reply: 超时 %.0fs", timeout_s)
            return False
        except Exception:
            logging.exception("wait_for_peer_reply 异常")
            return False

    def get_next_pool_message(self) -> str:
        """从消息池获取下一轮消息。"""
        if self._pool is None:
            self._logger.error("消息池未初始化")
            raise RuntimeError("消息池未初始化")
        return self._pool.next_message()

    def go_back_to_chat_list(self) -> bool:
        """从对话框返回聊天列表。

        按下 back 后验证是否仍在聊天页（检测 send_button/input_box），
        若是则再按一次 back。
        """
        try:
            self.driver.d.press("back")
            time.sleep(random.uniform(0.5, 1.0))
            self.driver.wait_ui_stable(max_wait=1.0)

            # 验证是否已离开聊天页：若 send_button 或 input_box 仍在，说明还在聊天页
            send_rid = self._get_rid("buttons", "send_button")
            input_rid = self._get_rid("buttons", "input_box")
            try:
                xml = self.driver.d.dump_hierarchy()
                still_on_chat = False
                if send_rid and send_rid in xml:
                    still_on_chat = True
                if input_rid and input_rid in xml:
                    still_on_chat = True
                if still_on_chat:
                    self._logger.warning(
                        "go_back_to_chat_list: 仍在聊天页（检测到 send_button/input_box），再次 back"
                    )
                    self.driver.d.press("back")
                    time.sleep(random.uniform(0.5, 1.0))
            except Exception:
                self._logger.debug(
                    "go_back_to_chat_list: 页面验证异常", exc_info=True
                )

            return True
        except Exception:
            logging.exception("go_back_to_chat_list 异常")
            return False

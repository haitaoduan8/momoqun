"""招呼扫描与逐个通过。"""

import logging
import random
import time
import xml.etree.ElementTree as ET
from typing import Optional

from core.driver import DeviceHandler
from utils.helpers import parse_bounds, random_delay


class GreetingScanner:
    """「收到的招呼」扫描器：读角标、进列表、逐个通过。"""

    def __init__(self, driver: DeviceHandler, elements: dict, settings: dict) -> None:
        self.driver = driver
        self.elements = elements
        self.settings = settings
        self._logger = logging.getLogger("greeter")

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
    def scan_badge(self) -> int:
        """扫描聊天列表页「收到的招呼」的角标数字。返回 >=0，异常时 0。"""
        try:
            entry_text = self._get_text("entry_elements", "sayhi_entry")
            badge_rid = self._get_rid("entry_elements", "red_dot")
            if not badge_rid:
                self._logger.warning("未配置 red_dot resourceId")
                return 0

            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)

            # 找 text=entry_text 的节点 bounds
            name_bounds = None
            for node in root.iter():
                if (node.attrib.get("text") or "") == entry_text:
                    b = parse_bounds(node.attrib.get("bounds", ""))
                    if b:
                        name_bounds = b
                        break

            if name_bounds is None:
                self._logger.debug("未在聊天列表中找到「%s」", entry_text)
                return 0

            _l, _t, _r, bt = name_bounds
            target_center_y = (_t + bt) // 2

            # 在同行内（center_y 接近）找 badge 节点
            for node in root.iter():
                rid = node.attrib.get("resource-id", "")
                if rid != badge_rid:
                    continue
                b = parse_bounds(node.attrib.get("bounds", ""))
                if b is None:
                    continue
                _nl, nt, _nr, nbt = b
                node_cy = (nt + nbt) // 2
                if abs(node_cy - target_center_y) < 120:
                    num_text = (node.attrib.get("text") or "").strip()
                    if num_text:
                        try:
                            return int(num_text)
                        except ValueError:
                            pass
                    # 可能数字在 content-desc 里
                    cd = (node.attrib.get("content-desc") or "").strip()
                    if cd:
                        try:
                            return int(cd)
                        except ValueError:
                            pass

            self._logger.debug("scan_badge: 找到「%s」但未解析到数字", entry_text)
            return 0
        except Exception:
            logging.exception("scan_badge 异常")
            return 0

    def enter_sayhi_list(self) -> bool:
        """点击「收到的招呼」进入招呼列表。返回 True 表示成功。"""
        try:
            entry_text = self._get_text("entry_elements", "sayhi_entry")
            if not entry_text:
                return False

            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)

            for node in root.iter():
                if (node.attrib.get("text") or "") == entry_text:
                    b = parse_bounds(node.attrib.get("bounds", ""))
                    if b:
                        cx = (b[0] + b[2]) // 2
                        cy = (b[1] + b[3]) // 2
                        self.driver.random_click_xy(cx, cy)
                        random_delay(self.settings)
                        self._logger.info("已点击「收到的招呼」")
                        return True

            self._logger.warning("未找到「%s」节点", entry_text)
            return False
        except Exception:
            logging.exception("enter_sayhi_list 异常")
            return False

    def _find_name_in_sayhi_item(self, accept_el) -> Optional[str]:
        """在招呼列表条目中，从「通过」按钮所在容器向上查找对方昵称。"""
        try:
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)

            # 获取「通过」按钮的 bounds
            el_info = accept_el.info
            if not el_info:
                return None
            el_bounds = el_info.get("bounds") or {}
            el_left = el_bounds.get("left", 0)
            el_top = el_bounds.get("top", 0)
            el_bottom = el_bounds.get("bottom", 0)

            best_name = None
            best_area = 0

            for node in root.iter():
                txt = (node.attrib.get("text") or "").strip()
                if not txt:
                    continue
                b = parse_bounds(node.attrib.get("bounds", ""))
                if b is None:
                    continue
                nl, nt, nr, nb = b
                # 候选节点应该与「通过」按钮在同一行（垂直方向接近）
                node_cy = (nt + nb) // 2
                btn_cy = (el_top + el_bottom) // 2
                if abs(node_cy - btn_cy) > 100:
                    continue
                # 名字应该在按钮左侧
                if nr >= el_left:
                    continue
                # 取同行中最左/面积最大的文本（通常是昵称）
                area = (nr - nl) * (nb - nt)
                txt_len = len(txt)
                # 优先选文本长度 2-15（昵称范围）
                if 1 <= txt_len <= 20 and area > best_area:
                    best_area = area
                    best_name = txt

            return best_name
        except Exception:
            self._logger.debug("_find_name_in_sayhi_item 异常", exc_info=True)
            return None

    def approve_one(self) -> Optional[dict]:
        """在招呼列表页点击第一个「通过」按钮，通过一个招呼。

        先识别对方昵称，再点通过。不再依赖点击后的自动跳转，
        由调用方自行回到聊天列表并通过昵称匹配进入对话框。

        返回 ``{"name": str}`` 或 None（失败时）。
        """
        try:
            accept_rid = self._get_rid("buttons", "accept_button")
            if not accept_rid:
                self._logger.warning("未配置 accept_button resourceId")
                return None

            el = self.driver.d(resourceId=accept_rid)
            if not el.exists:
                self._logger.warning("approve_one: 未找到「通过」按钮")
                return None

            # 点通过之前先尝试获取对方昵称
            name = self._find_name_in_sayhi_item(el)

            self.driver.click_uielement(el)
            random_delay(self.settings)

            result = {"name": name or None}
            self._logger.info("approve_one 完成: %s", result)
            return result
        except Exception:
            logging.exception("approve_one 异常")
            return None

    def go_back_to_chat_list(self) -> bool:
        """从任意界面按 back 返回到聊天列表。最多 3 次。"""
        try:
            row_rid = self._get_rid("chat_list", "chat_row")
            for i in range(3):
                try:
                    self.driver.d.press("back")
                except Exception:
                    self._logger.debug("back 按键异常", exc_info=True)
                time.sleep(random.uniform(0.5, 1.0))
                try:
                    xml = self.driver.d.dump_hierarchy()
                    if row_rid and row_rid in xml:
                        return True
                except Exception:
                    self._logger.debug("dump hierarchy 检测 chat_row 异常", exc_info=True)
            self._logger.warning("go_back_to_chat_list: 多次 back 后仍未检测到 chat_row")
            return False
        except Exception:
            logging.exception("go_back_to_chat_list 异常")
            return False

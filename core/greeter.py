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

            # 找到了「收到的招呼」入口但角标读不出数字 → 至少有 1 个新招呼
            self._logger.info("scan_badge: 找到「%s」但未解析到数字，假定至少 1 个", entry_text)
            return 1
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

    # UI 文案黑名单：这些不是用户昵称，不应被识别为好友名
    _NAME_BLACKLIST = {
        "拒绝", "通过", "取消", "确定", "关注", "消息", "设置",
        "添加", "删除", "完成", "返回", "发送", "保存", "更多",
        "收到的招呼", "互动通知", "订阅内容",
    }

    def _find_name_in_sayhi_item(self, accept_el) -> Optional[str]:
        """在招呼列表条目中，顺着「通过」按钮往 DOM 树上找父级容器，取容器内第一个文本节点作为昵称。"""
        try:
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)

            # 找到「通过」按钮在 DOM 中的节点
            el_info = accept_el.info
            if not el_info:
                return None
            el_rid = el_info.get("resourceName") or ""
            el_bounds = el_info.get("bounds") or {}
            el_top = el_bounds.get("top", 0)
            el_bottom = el_bounds.get("bottom", 0)
            el_left = el_bounds.get("left", 0)
            el_right = el_bounds.get("right", 0)

            btn_cy = (el_top + el_bottom) // 2

            def _valid_name(txt: str) -> bool:
                t = txt.strip()
                if not t or len(t) > 20:
                    return False
                if t in self._NAME_BLACKLIST:
                    return False
                return True

            # 策略 1：找 DOM 中与按钮同行、在按钮左侧的文本节点
            best_name = None
            best_left = 99999
            for node in root.iter():
                txt = (node.attrib.get("text") or "").strip()
                if not _valid_name(txt):
                    continue
                b = parse_bounds(node.attrib.get("bounds", ""))
                if b is None:
                    continue
                nl, nt, nr, nb = b
                node_cy = (nt + nb) // 2
                if abs(node_cy - btn_cy) > 100:
                    continue
                if nr > el_left + 30:   # 必须在按钮左侧
                    continue
                if nl < best_left:
                    best_left = nl
                    best_name = txt

            if best_name:
                self._logger.info("_find_name_in_sayhi_item 策略1命中: %s", best_name)
                return best_name

            # 策略 2：向上找父级容器，取容器内 bounds 最靠上/靠左的第一个短文本
            if el_rid:
                for node in root.iter():
                    if node.attrib.get("resource-id", "") != el_rid:
                        continue
                    parent = node
                    for _ in range(5):
                        prev = parent
                        for p in root.iter():
                            for c in p:
                                if c is parent:
                                    parent = p
                                    break
                        if prev is parent:
                            break
                        texts = []
                        for child in parent.iter():
                            t = (child.attrib.get("text") or "").strip()
                            cb = parse_bounds(child.attrib.get("bounds", ""))
                            if _valid_name(t) and cb:
                                texts.append((cb[0], t))  # (left, text)
                        texts.sort()
                        if texts:
                            self._logger.info(
                                "_find_name_in_sayhi_item 策略2命中: %s", texts[0][1]
                            )
                            return texts[0][1]
                    break

            self._logger.warning("_find_name_in_sayhi_item: 未识别到昵称")
            return None
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
        """从任意界面按 back 返回到聊天列表。最多 4 次。

        同时检测 chat_row 存在 且 accept_button 不存在，
        以区分主聊天列表和招呼子页面（两者都有 chat_row）。
        """
        try:
            row_rid = self._get_rid("chat_list", "chat_row")
            accept_rid = self._get_rid("buttons", "accept_button")
            for i in range(4):
                try:
                    self.driver.d.press("back")
                except Exception:
                    self._logger.debug("back 按键异常", exc_info=True)
                time.sleep(random.uniform(0.5, 1.0))
                self.driver.wait_ui_stable(max_wait=1.0)
                try:
                    xml = self.driver.d.dump_hierarchy()
                    if row_rid and row_rid in xml:
                        # 招呼子页面也有 chat_row，但还有 accept_button
                        if accept_rid and accept_rid in xml:
                            self._logger.debug(
                                "back 后仍在招呼子页面（检测到 accept_button），继续 back"
                            )
                            continue
                        self._logger.info(
                            "go_back_to_chat_list: 已回到主聊天列表 (尝试 %d 次)", i + 1
                        )
                        return True
                except Exception:
                    self._logger.debug("dump hierarchy 检测异常", exc_info=True)
            self._logger.warning(
                "go_back_to_chat_list: 多次 back 后仍未回到主聊天列表"
            )
            return False
        except Exception:
            logging.exception("go_back_to_chat_list 异常")
            return False

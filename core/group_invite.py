"""群聊邀请：进入群聊 → 群信息页 → 邀请好友 → 选好友 → 完成。

UI 元素皆从真机 dump 验证（OnePlus 8T + 陌陌渠道包，2026-05-21）。
"""

import logging
import random
import time
import xml.etree.ElementTree as ET
from typing import Optional

from core.driver import DeviceHandler
from utils.helpers import parse_bounds, random_delay


class GroupInviter:
    """群聊邀请管理器。"""

    def __init__(self, driver: DeviceHandler, elements: dict, settings: dict) -> None:
        self.driver = driver
        self.elements = elements
        self.settings = settings
        self._logger = logging.getLogger("group_invite")

    # ------------------------ 元素配置读取 ------------------------
    def _get_rid(self, *path: str):
        node: any = self.elements
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("resourceId") or None
        return None

    # ------------------------ 分辨率适配 ------------------------
    _REF_WIDTH = 1080  # OnePlus 8T 基准

    def _scale_x(self, px: int) -> int:
        try:
            w, _h = self.driver.d.window_size()
            return int(px * w / self._REF_WIDTH)
        except Exception:
            return px

    def _click_text(self, text: str, partial: bool = False) -> bool:
        """在当前界面 hierarchy 中查找 text 节点并点击其中心。"""
        try:
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)
            for node in root.iter():
                txt = (node.attrib.get("text") or "").strip()
                matched = (txt == text) if not partial else (text in txt)
                if not matched:
                    continue
                b = parse_bounds(node.attrib.get("bounds", ""))
                if b is None:
                    continue
                cx = (b[0] + b[2]) // 2
                cy = (b[1] + b[3]) // 2
                self._logger.info("点击 text=%r bounds=%s", txt, b)
                self.driver.random_click_xy(cx, cy)
                random_delay(self.settings)
                return True
            return False
        except Exception:
            logging.exception("_click_text 异常 text=%s", text)
            return False

    # ------------------------ 核心方法 ------------------------
    def enter_group(self, group_name: str) -> bool:
        """在聊天列表中找到指定群聊并点击进入。支持向下滚动翻找（最多 10 次）。

        真机验证：聊天列表行用 resourceId=chatlist_item_layout_top_part，
        行内昵称用 chatlist_item_tv_name。
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
                    self._logger.debug("dump hierarchy 异常")
                    time.sleep(0.5)
                    continue

                root = ET.fromstring(xml)
                for node in root.iter():
                    if node.attrib.get("resource-id") != row_rid:
                        continue

                    row_name = ""
                    for child in node.iter():
                        if child.attrib.get("resource-id") == name_rid:
                            row_name = (child.attrib.get("text") or "").strip()
                            break

                    if not row_name or row_name in ignore_names:
                        continue

                    if group_name in row_name:
                        self._logger.info(
                            "找到群聊: %s (scroll=%d)", group_name, scroll_attempt
                        )
                        b = parse_bounds(node.attrib.get("bounds", ""))
                        if b:
                            cx = (b[0] + b[2]) // 2
                            cy = (b[1] + b[3]) // 2
                            self.driver.random_click_xy(cx, cy)
                            random_delay(self.settings)
                            time.sleep(random.uniform(1.5, 2.5))
                            return True

                # 没找到，下翻
                try:
                    self.driver.swipe_scroll_down()
                except Exception:
                    self._logger.debug("滚动异常", exc_info=True)
                time.sleep(random.uniform(0.3, 0.6))

            self._logger.warning("未找到群聊「%s」", group_name)
            return False
        except Exception:
            logging.exception("enter_group 异常")
            return False

    def _detect_avatar_circle(self) -> tuple:
        """定位聊天列表中群头像的屏幕坐标。

        策略：通过 hierarchy 找群名节点，头像在其左边 109px 处。
        （OnePlus 8T 真机实测：img_avatar [45,784][210,949]，群名 left=236）

        如果头像在 AX 树中可见（resourceId=img_avatar），直接用其 bounds 中心。
        返回 (x, y) 或 (None, None)。
        """
        try:
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)

            # ── 策略 1：直接找 img_avatar 或 chatlist_item_iv_face ──
            for rid in ("com.immomo.momo:id/img_avatar",
                         "com.immomo.momo:id/chatlist_item_iv_face"):
                for node in root.iter():
                    if node.attrib.get("resource-id", "") != rid:
                        continue
                    b = parse_bounds(node.attrib.get("bounds", ""))
                    if b is None:
                        continue
                    # 验证这个头像旁边是不是目标群名
                    # 头像右边缘 ~210，群名左边缘 ~236，间隔 ~26px
                    # 向下找同行内的 chatlist_item_tv_name
                    ax = (b[0] + b[2]) // 2
                    ay = (b[1] + b[3]) // 2
                    row_cy = ay
                    for sub in root.iter():
                        if sub.attrib.get("resource-id", "") != \
                                "com.immomo.momo:id/chatlist_item_tv_name":
                            continue
                        sb = parse_bounds(sub.attrib.get("bounds", ""))
                        if sb is None:
                            continue
                        scy = (sb[1] + sb[3]) // 2
                        if abs(scy - row_cy) < 60:
                            txt = (sub.attrib.get("text") or "").strip()
                            if txt:
                                self._logger.info(
                                    "通过 img_avatar 找到头像: (%d,%d) 同行群名=%s",
                                    ax, ay, txt,
                                )
                                return ax, ay
                    # 即使没找到同行名，如果只有一个头像，大概率就是它
                    self._logger.info("通过 img_avatar 找到头像: (%d,%d)", ax, ay)
                    return ax, ay

            # ── 策略 2：通过群名推算 ──
            for node in root.iter():
                rid = node.attrib.get("resource-id", "")
                txt = (node.attrib.get("text") or "").strip()
                if rid == "com.immomo.momo:id/chatlist_item_tv_name" and txt:
                    b = parse_bounds(node.attrib.get("bounds", ""))
                    if b:
                        # 真机实测偏移：头像中心 = 群名左 - 109 (基于1080px宽)
                        off = self._scale_x(109)
                        ax = b[0] - off
                        ay = (b[1] + b[3]) // 2
                        self._logger.info(
                            "通过群名推算头像: (%d,%d) (name_left=%d offset=-%d)",
                            ax, ay, b[0],
                        )
                        return ax, ay

            return None, None

        except Exception:
            logging.exception("_detect_avatar_circle 异常")
            return None, None

    def enter_group_info_directly(self, group_name: str) -> bool:
        """在聊天列表中直接点群头像进入群信息页（不进群聊）。

        真机验证：消息列表中群头像 AX 可见（img_avatar），点击直接进入群信息。
        比「进群聊→点顶栏头像」少一步，更可靠。
        """
        self._logger.info("enter_group_info_directly: 在列表找「%s」的头像", group_name)

        try:
            row_rid = self._get_rid("chat_list", "chat_row")
            name_rid = self._get_rid("chat_list", "chat_row_name")
            ignore_names = set(self.settings.get("chat_ignore_names") or [])

            if not row_rid or not name_rid:
                self._logger.warning("缺少 chat_row/chat_row_name 配置")
                return False

            for scroll in range(10):
                xml = self.driver.d.dump_hierarchy()
                root = ET.fromstring(xml)

                for node in root.iter():
                    if node.attrib.get("resource-id") != row_rid:
                        continue

                    # 找行内群名
                    row_name = ""
                    for child in node.iter():
                        if child.attrib.get("resource-id") == name_rid:
                            row_name = (child.attrib.get("text") or "").strip()
                            break

                    if not row_name or row_name in ignore_names:
                        continue
                    if group_name not in row_name:
                        continue

                    self._logger.info("找到群「%s」(scroll=%d)", row_name, scroll)

                    # 在同行内找 img_avatar
                    avatar_center = None
                    for child in node.iter():
                        crid = child.attrib.get("resource-id", "")
                        if crid in ("com.immomo.momo:id/img_avatar",
                                     "com.immomo.momo:id/chatlist_item_iv_face"):
                            cb = parse_bounds(child.attrib.get("bounds", ""))
                            if cb:
                                avatar_center = ((cb[0] + cb[2]) // 2,
                                                  (cb[1] + cb[3]) // 2)
                                break

                    if avatar_center is None:
                        # fallback: 群名左 - 109 (基于1080px宽)
                        off = self._scale_x(109)
                        for child in node.iter():
                            if child.attrib.get("resource-id") == name_rid:
                                nb = parse_bounds(child.attrib.get("bounds", ""))
                                if nb:
                                    avatar_center = (nb[0] - off,
                                                      (nb[1] + nb[3]) // 2)
                                break

                    if avatar_center:
                        self._logger.info("点击群头像: (%d,%d)", *avatar_center)
                        self.driver.random_click_xy(*avatar_center)
                        random_delay(self.settings)
                        time.sleep(random.uniform(1.5, 2.5))

                        # 验证
                        xml2 = self.driver.d.dump_hierarchy()
                        if "群成员" in xml2 or "群号" in xml2:
                            self._logger.info("已进入群信息页")
                            return True
                        self._logger.warning("点击头像后未进入群信息页")
                        return False

                    self._logger.warning("找到群名但无法定位头像")
                    return False

                # 下翻
                try:
                    self.driver.swipe_scroll_down()
                except Exception:
                    self._logger.debug("滚动异常", exc_info=True)
                time.sleep(random.uniform(0.3, 0.6))

            self._logger.warning("未在聊天列表中找到「%s」", group_name)
            return False
        except Exception:
            logging.exception("enter_group_info_directly 异常")
            return False

    def open_group_info(self) -> bool:
        """从群聊页进入群信息页。

        方案 A（优先）：OpenCV 圆圈检测定位群头像 → 点击
        方案 B：固定坐标 (350, 190) 点击
        方案 C：点击群名 title_textview
        方案 D：点击 group_chat_title_layout
        """
        try:
            # ── 方案 A：圆圈检测群头像 ──
            self._logger.info("open_group_info: 圆圈检测群头像...")
            ax, ay = self._detect_avatar_circle()
            if ax is not None:
                self.driver.random_click_xy(ax, ay)
                time.sleep(random.uniform(1.5, 2.0))
                xml = self.driver.d.dump_hierarchy()
                if "群成员" in xml or "群号" in xml:
                    self._logger.info("方案 A (圆圈检测) 成功，坐标 (%d,%d)", ax, ay)
                    return True
                self._logger.info("方案 A 未命中，坐标 (%d,%d)", ax, ay)

            # ── 方案 B：固定坐标 ──
            self._logger.info("方案 B: 固定坐标 (350, 190)")
            self.driver.random_click_xy(350, 190)
            time.sleep(random.uniform(1.5, 2.0))
            xml = self.driver.d.dump_hierarchy()
            if "群成员" in xml or "群号" in xml:
                self._logger.info("方案 B 成功")
                return True

            # ── 方案 C：点击群名 ──
            self._logger.info("方案 C: 点击群名 title")
            self._click_text("交友")
            time.sleep(random.uniform(1.5, 2.0))
            xml = self.driver.d.dump_hierarchy()
            if "群成员" in xml or "群号" in xml:
                self._logger.info("方案 C 成功")
                return True

            # ── 方案 D：点击 title layout ──
            self._logger.info("方案 D: group_chat_title_layout")
            el = self.driver.d(
                resourceId="com.immomo.momo:id/group_chat_title_layout"
            )
            if el.exists:
                self.driver.click_uielement(el)
                time.sleep(random.uniform(1.5, 2.0))
                xml = self.driver.d.dump_hierarchy()
                if "群成员" in xml or "群号" in xml:
                    self._logger.info("方案 D 成功")
                    return True

            self._logger.warning("所有方案均未进入群信息页")
            return False
        except Exception:
            logging.exception("open_group_info 异常")
            return False

    def open_invite_panel(self) -> bool:
        """在群信息页点击邀请按钮进入邀请面板。

        真机验证：「邀请好友」是文字标签，真正的按钮是它上方的
        ImageView [45,1837][225,2017]（可点击）。
        """
        self._logger.info("open_invite_panel: 查找邀请按钮...")

        try:
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)

            # 策略：找 text="邀请好友" 的节点，再找它上方的可点击 ImageView
            invite_text_node = None
            for node in root.iter():
                if (node.attrib.get("text") or "").strip() == "邀请好友":
                    invite_text_node = node
                    break

            if invite_text_node is not None:
                # 在父级中找可点击的 ImageView
                parent = invite_text_node
                for _ in range(3):
                    for p in root.iter():
                        for c in p:
                            if c == parent:
                                parent = p
                                break

                for child in parent.iter():
                    crid = child.attrib.get("resource-id", "")
                    ccls = child.attrib.get("class", "")
                    cclickable = child.attrib.get("clickable", "")
                    if cclickable == "true" and "Image" in ccls:
                        cb = parse_bounds(child.attrib.get("bounds", ""))
                        if cb:
                            cx = (cb[0] + cb[2]) // 2
                            cy = (cb[1] + cb[3]) // 2
                            self._logger.info("点击邀请按钮 ImageView: (%d,%d)", cx, cy)
                            self.driver.random_click_xy(cx, cy)
                            random_delay(self.settings)
                            time.sleep(random.uniform(1.0, 1.5))

                            xml2 = self.driver.d.dump_hierarchy()
                            if "取消" in xml2 and "完成" in xml2:
                                self._logger.info("已进入邀请好友面板")
                                return True
                            self._logger.warning("点击邀请按钮后未进入邀请面板")
                            return False

            # fallback: 找包含"邀请好友"文字区域的任何可点击节点
            for node in root.iter():
                if node.attrib.get("clickable") != "true":
                    continue
                b = parse_bounds(node.attrib.get("bounds", ""))
                if b is None:
                    continue
                cls = node.attrib.get("class", "")
                if "Image" not in cls:
                    continue
                # 应该在 y=1800~2200 范围内
                if 1800 < b[1] < 2200 and b[0] < 250:
                    cx = (b[0] + b[2]) // 2
                    cy = (b[1] + b[3]) // 2
                    self._logger.info("fallback: 点击可点击 ImageView (%d,%d)", cx, cy)
                    self.driver.random_click_xy(cx, cy)
                    random_delay(self.settings)
                    time.sleep(random.uniform(1.0, 1.5))
                    xml2 = self.driver.d.dump_hierarchy()
                    if "取消" in xml2 and "完成" in xml2:
                        self._logger.info("已进入邀请好友面板")
                        return True

            self._logger.warning("未找到邀请按钮")
            return False
        except Exception:
            logging.exception("open_invite_panel 异常")
            return False

    def select_friend(self, friend_name: str) -> bool:
        """在邀请面板中查找并点击好友名字以勾选。

        真机验证：
        - 邀请面板中好友按 tab 分组：「最近」「好友」
        - 优先在「好友」tab 中查找
        - 好友名字显示为 text 节点，如 text="星星" bounds=[219,579][963,647]
        - 点击后标题会变成「邀请好友(1)」
        - 如果当前屏没有，可向下滚动

        注意：点名字本身即可勾选，不需要单独的 checkbox。
        """
        self._logger.info("select_friend: 查找 %s", friend_name)

        # 先切到「好友」tab
        for tab_text in ["好友", "最近"]:
            if self._click_text(tab_text):
                time.sleep(random.uniform(0.3, 0.6))
                break

        # 查找好友（可能需滚动）
        for scroll in range(8):
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)

            for node in root.iter():
                txt = (node.attrib.get("text") or "").strip()
                if txt == friend_name:
                    self._logger.info(
                        "找到好友: %s (scroll=%d)", friend_name, scroll
                    )
                    b = parse_bounds(node.attrib.get("bounds", ""))
                    if b:
                        cx = (b[0] + b[2]) // 2
                        cy = (b[1] + b[3]) // 2
                        self.driver.random_click_xy(cx, cy)
                        random_delay(self.settings)
                        time.sleep(random.uniform(0.5, 1.0))

                        # 验证选中
                        xml2 = self.driver.d.dump_hierarchy()
                        if "邀请好友(1)" in xml2:
                            self._logger.info("好友 %s 已选中", friend_name)
                            return True
                        else:
                            self._logger.warning(
                                "点击后未检测到选中状态，可能需再点一次"
                            )
                            # 重试一次
                            self.driver.random_click_xy(cx, cy)
                            time.sleep(random.uniform(0.5, 1.0))
                            xml2 = self.driver.d.dump_hierarchy()
                            if "邀请好友(1)" in xml2:
                                self._logger.info("重试后选中成功")
                                return True

            # 没找到，下翻
            self._logger.debug("当前屏未找到 %s，下翻 (scroll=%d)", friend_name, scroll)
            try:
                self.driver.swipe_scroll_down()
            except Exception:
                self._logger.debug("滚动异常", exc_info=True)
            time.sleep(random.uniform(0.4, 0.7))

        self._logger.warning("未在邀请面板中找到 %s", friend_name)
        return False

    def confirm_invite(self) -> bool:
        """点击右上角「完成」按钮确认邀请。

        真机验证：text="完成" 位于 [915,220][1011,352]。
        """
        self._logger.info("confirm_invite: 点击「完成」")
        if self._click_text("完成"):
            time.sleep(random.uniform(1.5, 2.5))
            self._logger.info("邀请确认完成")
            return True
        return False

    def go_back_to_chat_list(self) -> bool:
        """从群聊/群信息页一路返回到聊天列表。多次按 back。"""
        row_rid = self._get_rid("chat_list", "chat_row")
        try:
            for i in range(5):
                try:
                    self.driver.d.press("back")
                except Exception:
                    self._logger.debug("back 异常", exc_info=True)
                time.sleep(random.uniform(0.5, 1.0))
                # 检查是否回到聊天列表
                try:
                    xml = self.driver.d.dump_hierarchy()
                    if row_rid and row_rid in xml:
                        self._logger.info("已回到聊天列表")
                        return True
                except Exception:
                    pass
            return True  # 尽力了
        except Exception:
            logging.exception("go_back_to_chat_list 异常")
            return False

    # ------------------------ 拉黑好友 ------------------------
    def block_friend(self, friend_name: str) -> bool:
        """拉黑指定好友。

        真机验证流程：
        1. 聊天列表找到好友 → 进对话框
        2. 点右上角 chat_toolbar_avatar → 聊天设置页
        3. 点「拉黑」文字 → 确认弹窗
        4. 点弹窗中「拉黑」(button1) → 完成
        5. 返回聊天列表
        """
        self._logger.info("block_friend: 拉黑 %s", friend_name)

        try:
            # ── Step 1: 进对话框 ──
            row_rid = self._get_rid("chat_list", "chat_row")
            name_rid = self._get_rid("chat_list", "chat_row_name")

            found = False
            for scroll in range(8):
                xml = self.driver.d.dump_hierarchy()
                root = ET.fromstring(xml)
                for node in root.iter():
                    if node.attrib.get("resource-id") != row_rid:
                        continue
                    row_name = ""
                    for child in node.iter():
                        if child.attrib.get("resource-id") == name_rid:
                            row_name = (child.attrib.get("text") or "").strip()
                            break
                    if friend_name in row_name:
                        b = parse_bounds(node.attrib.get("bounds", ""))
                        if b:
                            cx = (b[0] + b[2]) // 2
                            cy = (b[1] + b[3]) // 2
                            self.driver.random_click_xy(cx, cy)
                            random_delay(self.settings)
                            time.sleep(random.uniform(1.0, 1.5))
                            found = True
                            break
                if found:
                    break
                try:
                    self.driver.swipe_scroll_down()
                except Exception:
                    pass
                time.sleep(random.uniform(0.3, 0.5))

            if not found:
                self._logger.warning("未在聊天列表中找到 %s", friend_name)
                return False

            # ── Step 2: 点右上角头像 → 聊天设置 ──
            avatar_rid = self._get_rid("block_friend", "toolbar_avatar")
            if avatar_rid:
                el = self.driver.d(resourceId=avatar_rid)
                if el.exists:
                    self.driver.click_uielement(el)
                else:
                    # fallback: chat_toolbar_avatar 一般在 x=996, y=187
                    self.driver.random_click_xy(996, 187)
            else:
                self.driver.random_click_xy(996, 187)
            random_delay(self.settings)
            time.sleep(random.uniform(1.0, 1.5))

            # ── Step 3: 找「拉黑」文字并点击 ──
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)
            clicked = False
            for node in root.iter():
                if (node.attrib.get("text") or "").strip() == "拉黑":
                    b = parse_bounds(node.attrib.get("bounds", ""))
                    if b:
                        cx = (b[0] + b[2]) // 2
                        cy = (b[1] + b[3]) // 2
                        self.driver.random_click_xy(cx, cy)
                        random_delay(self.settings)
                        time.sleep(random.uniform(1.0, 1.5))
                        clicked = True
                        break
            if not clicked:
                self._logger.warning("未找到「拉黑」文字")
                self.go_back_to_chat_list()
                return False

            # ── Step 4: 确认弹窗中再点「拉黑」─
            confirm_rid = self._get_rid("block_friend", "confirm_block_button")
            if confirm_rid:
                el = self.driver.d(resourceId=confirm_rid, text="拉黑")
                if el.exists:
                    self.driver.click_uielement(el)
                else:
                    self.driver.random_click_xy(873, 1402)
            else:
                self.driver.random_click_xy(873, 1402)
            time.sleep(random.uniform(1.0, 1.5))
            self._logger.info("已拉黑 %s", friend_name)

            # ── Step 5: 回聊天列表 ──
            self.go_back_to_chat_list()
            return True

        except Exception:
            logging.exception("block_friend 异常")
            try:
                self.go_back_to_chat_list()
            except Exception:
                pass
            return False

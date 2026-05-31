"""招呼扫描与逐个通过。"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Optional

from core.driver import DeviceHandler
from utils.helpers import ElementsConfig, parse_bounds, random_delay


class GreetingScanner:
    """「收到的招呼」扫描器：读角标、进列表、逐个通过。"""

    def __init__(self, driver: DeviceHandler, elements: dict, settings: dict) -> None:
        self.driver = driver
        self.elements = elements
        self.settings = settings
        self._ec = ElementsConfig(elements)
        self._logger = logging.getLogger("greeter")

    # ------------------------ 元素配置读取（委托 ElementsConfig）-------------------------
    def _get_rid(self, *path: str) -> Optional[str]:
        return self._ec.get_rid(*path)

    def _get_text(self, *path: str) -> Optional[str]:
        return self._ec.get_text(*path)

    # ------------------------ 核心方法 ------------------------
    def scan_badge(self) -> int:
        """扫描聊天列表页「收到的招呼」的未读角标。返回 >=0，异常时 0。

        判定语义（严格）：
          - 必须同时满足「入口节点存在」**且**「同行内存在 ``red_dot``
            (``chatlist_item_tv_status_new``) 节点」，才算有新招呼；
          - 若入口同行的下方/旁边 ``chatlist_item_tv_content`` 文本为
            「暂无新招呼」之类，直接返回 0；
          - 兜底：找到 badge 节点但 text/content-desc 都不是数字 → 返回 1。

        历史上这里的兜底把"找到入口"误当成"有新招呼"，导致每轮假阳性进招呼页。
        """
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

            # 早返：同行内若有「暂无新招呼」之类文本，直接 0
            for node in root.iter():
                t = (node.attrib.get("text") or "").strip()
                if not t:
                    continue
                if "暂无新招呼" not in t:
                    continue
                b = parse_bounds(node.attrib.get("bounds", ""))
                if not b:
                    continue
                node_cy = (b[1] + b[3]) // 2
                if abs(node_cy - target_center_y) < 200:
                    self._logger.debug("scan_badge: 同行检出「暂无新招呼」")
                    return 0

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
                    # 找到 badge 但文本不是数字 → 至少 1 个
                    self._logger.info(
                        "scan_badge: 找到 red_dot 节点但 text/content-desc 非数字，假定 1 个"
                    )
                    return 1

            # 入口存在但同行无 red_dot → 没有新招呼
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

    # UI 文案黑名单：这些是按钮/标签文本，绝不会是好友昵称。
    _NAME_BLACKLIST = {
        "拒绝", "通过", "取消", "确定", "关注", "消息", "设置",
        "添加", "删除", "完成", "返回", "发送", "保存", "更多",
        "回复", "忽略", "列表",
        "收到的招呼", "互动通知", "订阅内容",
    }

    def _find_active_sayhi_name(self, root: ET.Element) -> Optional[str]:
        """识别当前最顶层招呼卡片的昵称。

        招呼详情页是「卡片堆叠」结构：一次只能通过最上面一张卡片，
        其他卡片以缩小的预览堆在下方/上方。三张卡片都含
        ``com.immomo.momo:id/tv_name`` 节点，但只有最顶层那张是当前可操作的。

        判定规则（按稳定性排序，组合使用）：
          1. ``tv_name`` 必须在「通过」按钮上方（y_bottom < confirm_btn.top），
             否则可能是 footer 区域的混淆文本；
          2. height ≥ 30，过滤被裁切到只剩个标点的堆叠预览；
          3. 优先 height 最大（顶层卡片字号最大），同 height 时取 y_bottom 最大
             （视觉上最贴近按钮，即活动卡片）。

        命中失败返回 ``None``，调用方应入库 ``unknown`` 兜底。
        """
        name_rid = self._get_rid("entry_elements", "sayhi_card_name") or "com.immomo.momo:id/tv_name"
        btn_rid = self._get_rid("buttons", "accept_button")

        try:
            btn_top: Optional[int] = None
            if btn_rid:
                for n in root.iter():
                    if n.attrib.get("resource-id") == btn_rid:
                        b = parse_bounds(n.attrib.get("bounds", ""))
                        if b:
                            btn_top = b[1]
                            break

            candidates = []
            for n in root.iter():
                if n.attrib.get("resource-id") != name_rid:
                    continue
                b = parse_bounds(n.attrib.get("bounds", ""))
                txt = (n.attrib.get("text") or "").strip()
                if not b or not txt:
                    continue
                if btn_top is not None and b[1] >= btn_top:
                    continue
                if txt in self._NAME_BLACKLIST:
                    continue
                if len(txt) > 20:
                    continue
                h = b[3] - b[1]
                if h < 30:
                    continue
                candidates.append((h, b[3], txt, b))

            if not candidates:
                self._logger.warning(
                    "_find_active_sayhi_name: 未发现可用 tv_name (name_rid=%s btn_top=%s)",
                    name_rid,
                    btn_top,
                )
                return None

            candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            h, yb, txt, b = candidates[0]
            self._logger.info(
                "_find_active_sayhi_name 命中: %r (height=%d y_bottom=%d bounds=%s 候选数=%d)",
                txt, h, yb, b, len(candidates),
            )
            return txt
        except Exception:
            self._logger.exception("_find_active_sayhi_name 异常")
            return None

    def approve_one(self) -> Optional[dict]:
        """通过当前最顶层招呼卡片，先识别昵称再点击。

        返回 ``{"name": str}``（昵称未识别到时 ``name`` 为 None），失败返回 None。
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

            name: Optional[str] = None
            try:
                xml = self.driver.d.dump_hierarchy()
                root = ET.fromstring(xml)
                name = self._find_active_sayhi_name(root)
            except Exception:
                self._logger.exception("approve_one: dump_hierarchy/解析失败")

            self.driver.click_uielement(el)
            random_delay(self.settings)

            result = {"name": name or None}
            self._logger.info("approve_one 完成: %s", result)
            return result
        except Exception:
            logging.exception("approve_one 异常")
            return None

    def go_back_to_chat_list(self) -> bool:
        """从任意界面按 back 返回到聊天列表。"""
        from utils.helpers import go_back_to_chat_list as _shared_back
        return _shared_back(
            self.driver, self.elements, max_backs=4, logger=self._logger,
        )

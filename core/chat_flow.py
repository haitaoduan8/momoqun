"""聊天列表遍历回复流程。

基于 Momo_Project 的 TraversalRunner + ChatListUiSource 架构重写。

核心思路：
- ChatListUiSource：基于 UIAutomator hierarchy 的动态候选源，负责扫屏、下翻、到底判定、回顶
- ChatFlow：业务装配，组合 TraversalRunner 实现对聊天列表的不重不漏遍历
- reply_one：单次回复动作（点开会话 → 发送消息 → 标记状态 → 返回列表）
"""

from __future__ import annotations

import logging
import random
import re
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from actions.chat_topbar import handle_chat_topbar_friend_actions
from actions.chat_unread_badge import extract_row_meta
from actions.ui_hierarchy import _safe_dump_hierarchy
from actions.mutual_friend import detect_mutual_friend_by_voice_button
from actions.scroll_engine import smooth_scroll_up
from core.driver import DeviceHandler
from core.message_pool import MessagePoolManager
from core.traversal import Candidate, CandidateSource, TraversalRunner, TraversalReport
from data.storage import StorageHandler

BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def _parse_bounds(raw: str) -> Optional[Dict[str, int]]:
    m = BOUNDS_RE.fullmatch(raw or "")
    if not m:
        return None
    left, top, right, bottom = map(int, m.groups())
    if right <= left or bottom <= top:
        return None
    return {"left": left, "top": top, "right": right, "bottom": bottom}


# ---------------------------------------------------------------------------
# ChatListUiSource
# ---------------------------------------------------------------------------


class ChatListUiSource(CandidateSource):
    """基于 UI hierarchy 的聊天列表候选源。

    - full_list_mode=True：下翻 → 尾部 uid 稳定 → 到底 → 回顶 → 指纹收敛
    - full_list_mode=False：只回顶 + 指纹收敛（只关心顶部活跃会话）
    """

    def __init__(
        self,
        driver: DeviceHandler,
        elements: Dict[str, Any],
        *,
        already_done: Callable[[str], bool],
        full_list_mode: bool = True,
        scroll_to_top: Optional[Callable[[], None]] = None,
        stable_cycles_to_exhaust: int = 2,
        max_advance: int = 64,
        scroll_ratio: float = 0.75,
        bottom_stable_cycles: int = 2,
        settle_delay_ms: int = 350,
        ignore_names: Optional[Iterable[Any]] = None,
        exit_on_bottom: bool = False,
        logger: Optional[logging.Logger] = None,
        recover_to_chat_list: Optional[Callable[[], None]] = None,
        visible_extra_filter: Optional[Callable[[Candidate], bool]] = None,
    ) -> None:
        self.driver = driver
        self.elements = elements or {}
        self.already_done = already_done
        self.full_list_mode = bool(full_list_mode)
        self._external_scroll_to_top = scroll_to_top
        self.stable_cycles_to_exhaust = max(1, int(stable_cycles_to_exhaust))
        self.max_advance = max(1, int(max_advance))
        try:
            sr = float(scroll_ratio)
        except (TypeError, ValueError):
            sr = 0.75
        self.scroll_ratio = min(0.95, max(0.2, sr))
        self.bottom_stable_cycles = max(1, int(bottom_stable_cycles))
        self.settle_delay_ms = max(0, int(settle_delay_ms))
        self.ignore_names = self._normalize_ignore_names(ignore_names)
        self.exit_on_bottom = bool(exit_on_bottom)
        self.log = logger or logging.getLogger(__name__)

        self._last_fingerprint: Optional[Tuple[str, ...]] = None
        self._stable_count = 0
        self._advance_count = 0
        self._last_tail_uid: Optional[str] = None
        self._tail_stable_count = 0
        self._saw_list_bottom: bool = False
        self._recover_to_chat_list = recover_to_chat_list
        self._visible_extra_filter = visible_extra_filter

    @staticmethod
    def _normalize_ignore_names(raw_names: Optional[Iterable[Any]]) -> set:
        names = set()
        try:
            for raw in raw_names or []:
                name = str(raw).strip()
                if name:
                    names.add(name)
        except Exception:
            logging.exception("解析聊天忽略名单失败")
        return names

    def _is_ignored(self, cand: Candidate) -> bool:
        if not self.ignore_names:
            return False
        values = (cand.name, cand.uid)
        return any(str(v).strip() in self.ignore_names for v in values if v is not None)

    # ------------------------ 元素配置读取 ------------------------
    def _get_rid(self, *path: str) -> Optional[str]:
        node: Any = self.elements
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("resourceId")
        return None

    def _get_text(self, *path: str) -> Optional[str]:
        node: Any = self.elements
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("text")
        return None

    @staticmethod
    def _root_has_resource_id(root: ET.Element, rid: str) -> bool:
        if not rid:
            return False
        try:
            for node in root.iter():
                if (node.attrib.get("resource-id") or "") == rid:
                    return True
        except Exception:
            logging.debug("_root_has_resource_id 遍历异常", exc_info=True)
        return False

    # ------------------------ UI 操作 ------------------------
    def _dump(self) -> Optional[ET.Element]:
        try:
            xml = _safe_dump_hierarchy(self.driver)
            if not xml:
                return None
            return ET.fromstring(xml)
        except Exception:
            self.log.exception("dump_hierarchy 失败")
            return None

    def _scroll_to_top(self) -> None:
        if self._external_scroll_to_top is not None:
            try:
                self._external_scroll_to_top()
                return
            except Exception:
                self.log.exception("外部 scroll_to_top 异常，改用内置策略")
        row_rid = self._get_rid("chat_list", "chat_row")
        if row_rid:
            try:
                self.driver.d(resourceId=row_rid).fling.toBeginning(max_swipes=10)
                return
            except Exception:
                self.log.debug("列表 fling 回顶失败，改用手势")
        self._scroll_to_top_swipe_fallback()

    def _scroll_to_top_swipe_fallback(self) -> None:
        try:
            w, h = self.driver.d.window_size()
            x = int(w * 0.5)
            y1 = int(h * 0.32)
            y2 = int(h * 0.72)
            for _ in range(3):
                self.driver.d.swipe(x, y1, x, y2, 0.25)
                time.sleep(0.25 + random.uniform(0.0, 0.2))
        except Exception:
            self.log.exception("内置手势 scroll_to_top 异常")

    def _settle_delay(self) -> None:
        base = self.settle_delay_ms / 1000.0
        if base <= 0:
            return
        jitter = base * 0.3
        time.sleep(max(0.0, base + random.uniform(-jitter, jitter)))

    def _list_bounds_from_rows(self, root: ET.Element) -> Optional[Dict[str, int]]:
        row_rid = self._get_rid("chat_list", "chat_row")
        if not row_rid:
            return None
        tops, bottoms, lefts, rights = [], [], [], []
        for node in root.iter():
            if node.attrib.get("resource-id") != row_rid:
                continue
            b = _parse_bounds(node.attrib.get("bounds", ""))
            if b is None:
                continue
            tops.append(b["top"])
            bottoms.append(b["bottom"])
            lefts.append(b["left"])
            rights.append(b["right"])
        if not tops:
            return None
        return {
            "left": min(lefts),
            "top": min(tops),
            "right": max(rights),
            "bottom": max(bottoms),
        }

    def _scroll_list_down_one(self) -> None:
        """三档降级下翻：resourceId 滚动 → 列表域减速拖拽 → 全屏手势。"""
        sc = self._get_rid("chat_list", "list_scroller")
        if sc:
            try:
                o = self.driver.d(resourceId=sc)
                if o.exists:
                    o.scroll.vert.forward(50)
                    self._settle_delay()
                    return
            except Exception:
                self.log.debug("list_scroller 下翻失败，改用列表域手势", exc_info=True)

        root = self._dump()
        list_bounds = self._list_bounds_from_rows(root) if root is not None else None
        if list_bounds is not None:
            try:
                height = list_bounds["bottom"] - list_bounds["top"]
                swipe_px = int(height * self.scroll_ratio)
                if swipe_px > 0 and smooth_scroll_up(
                    self.driver.d, list_bounds, swipe_px
                ):
                    self._settle_delay()
                    return
                self.log.debug("smooth_scroll_up 返回 False，回退全屏手势")
            except Exception:
                self.log.debug("smooth_scroll_up 异常，回退全屏手势", exc_info=True)

        self.log.warning("ChatListUiSource 下翻列表回退到全屏手势")
        try:
            w, h = self.driver.d.window_size()
            x = int(w * 0.5) + random.randint(-5, 5)
            y1 = int(h * 0.72)
            y2 = int(h * 0.32)
            self.driver.d.swipe(x, y1, x, y2, 0.22)
            self._settle_delay()
        except Exception:
            self.log.exception("手势下翻列表异常")

    # ------------------------ 节点提取 ------------------------
    def _extract_rows(self, root: ET.Element) -> List[Candidate]:
        row_rid = self._get_rid("chat_list", "chat_row")
        if not row_rid:
            self.log.warning("chat_list.chat_row.resourceId 未配置")
            return []

        rows: List[Candidate] = []
        for node in root.iter():
            if node.attrib.get("resource-id") != row_rid:
                continue

            meta = extract_row_meta(node, self.elements)
            if meta is None:
                continue

            uid = meta.get("uid")
            name = meta.get("name")
            has_unread = bool(meta.get("has_unread"))
            bounds = meta.get("bounds")

            if not uid:
                uid = name or f"anon-{uuid.uuid4().hex[:10]}"

            rows.append(
                Candidate(
                    uid=str(uid),
                    name=name,
                    meta={"bounds": bounds, "has_unread": has_unread},
                )
            )

        rows.sort(key=lambda c: (c.meta.get("bounds") or {}).get("top", 0))
        deduped: List[Candidate] = []
        seen = set()
        for c in rows:
            if c.uid in seen:
                continue
            seen.add(c.uid)
            deduped.append(c)
        return deduped

    def _fingerprint(self, rows: List[Candidate]) -> Tuple[str, ...]:
        return tuple(c.uid for c in rows)

    @staticmethod
    def _tail_uid(rows: List[Candidate]) -> Optional[str]:
        return rows[-1].uid if rows else None

    def _is_single_screen(self, rows: List[Candidate]) -> bool:
        """首屏已包含全部聊天行（无需下滑）。"""
        if len(rows) <= 3:
            return True
        try:
            h = self.driver.d.window_size()[1]
        except Exception:
            return False
        for c in rows:
            b = c.meta.get("bounds") if isinstance(c.meta, dict) else None
            if b and b.get("bottom", 0) > h * 0.85:
                return False
        return True

    # ------------------------ CandidateSource 接口 ------------------------
    def fetch_visible(self) -> List[Candidate]:
        root = self._dump()
        if root is None:
            return []
        rows = self._extract_rows(root)

        # 修复：如果不在聊天列表（没 row 但有输入框），尝试恢复
        input_rid = self._get_rid("buttons", "input_box")
        if (
            not rows
            and input_rid
            and self._recover_to_chat_list is not None
            and self._root_has_resource_id(root, input_rid)
        ):
            try:
                self.log.warning("无 chat_row 但含输入框，疑滞留私聊，执行恢复")
                self._recover_to_chat_list()
            except Exception:
                self.log.exception("recover_to_chat_list 异常")
            try:
                time.sleep(random.uniform(0.15, 0.45))
            except Exception:
                pass
            root = self._dump()
            if root is None:
                return []
            rows = self._extract_rows(root)

        fp = self._fingerprint(rows)
        if fp == self._last_fingerprint:
            self._stable_count += 1
        else:
            self._stable_count = 0
            self._last_fingerprint = fp

        visible: List[Candidate] = []
        for c in rows:
            if self._is_ignored(c):
                continue
            # 有未读消息 或 未被 already_done → 作为候选
            if c.meta.get("has_unread") or not self.already_done(c.uid):
                if self._visible_extra_filter is not None:
                    try:
                        if not self._visible_extra_filter(c):
                            continue
                    except Exception:
                        logging.exception("visible_extra_filter 异常 uid=%s", c.uid)
                        continue
                visible.append(c)
        return visible

    def _advance_retop_only(self) -> bool:
        if self._advance_count >= self.max_advance:
            return False
        self._advance_count += 1
        before = self._last_fingerprint
        self._scroll_to_top()
        try:
            self.driver.wait_ui_stable(max_wait=1.0)
        except Exception:
            self.log.debug("wait_ui_stable 异常（忽略）", exc_info=True)
        root = self._dump()
        if root is None:
            return False
        fp = self._fingerprint(self._extract_rows(root))
        self._last_fingerprint = fp
        changed = fp != before
        if not changed:
            self._stable_count += 1
        else:
            self._stable_count = 0
        return bool(changed)

    def advance(self) -> bool:
        if not self.full_list_mode:
            return self._advance_retop_only()

        if self._advance_count >= self.max_advance:
            return False
        self._advance_count += 1

        root = self._dump()
        if root is None:
            return False
        rows_before = self._extract_rows(root)
        tail_before = self._tail_uid(rows_before)

        # 单屏检测：行数少且最后一行未接近屏幕底部 → 直接判到底
        if self._advance_count == 1 and self._is_single_screen(rows_before):
            self.log.debug("首屏已包含全部聊天行（%d 行），跳过后继滑动", len(rows_before))
            self._saw_list_bottom = True
            self._last_fingerprint = self._fingerprint(rows_before)
            self._last_tail_uid = tail_before
            self._tail_stable_count = 0
            return True

        # 已到底：不再下翻，只做回顶+指纹收束
        if self._saw_list_bottom:
            before = self._last_fingerprint
            self._scroll_to_top()
            try:
                self.driver.wait_ui_stable(max_wait=1.0)
            except Exception:
                self.log.debug("wait_ui_stable 异常（忽略）", exc_info=True)
            root2 = self._dump()
            if root2 is None:
                return False
            fp = self._fingerprint(self._extract_rows(root2))
            self._last_fingerprint = fp
            changed = fp != before
            if not changed:
                self._stable_count += 1
            else:
                self._stable_count = 0
            return bool(changed)

        self._scroll_list_down_one()
        try:
            self.driver.wait_ui_stable(max_wait=1.0)
        except Exception:
            self.log.debug("wait_ui_stable 异常（忽略）", exc_info=True)
        root2 = self._dump()
        if root2 is None:
            return True
        after_rows = self._extract_rows(root2)
        tail_after = self._tail_uid(after_rows)

        if tail_after is not None and tail_after != tail_before:
            self._last_fingerprint = self._fingerprint(after_rows)
            self._last_tail_uid = tail_after
            self._tail_stable_count = 0
            self._stable_count = 0
            return True

        self._tail_stable_count += 1
        self._last_tail_uid = tail_after
        if self._tail_stable_count < self.bottom_stable_cycles:
            return True

        self._saw_list_bottom = True

        if self.exit_on_bottom:
            self._last_fingerprint = self._fingerprint(after_rows)
            self._stable_count = self.stable_cycles_to_exhaust
            return False

        self._scroll_to_top()
        try:
            self.driver.wait_ui_stable(max_wait=1.0)
        except Exception:
            self.log.debug("wait_ui_stable 异常（忽略）", exc_info=True)
        retop_rows = self._extract_rows(self._dump() or ET.fromstring("<root/>"))
        self._last_fingerprint = self._fingerprint(retop_rows)
        self._last_tail_uid = self._tail_uid(retop_rows)
        self._stable_count = 0
        self._tail_stable_count = 0
        return True

    def is_exhausted(self) -> bool:
        if self._advance_count >= self.max_advance:
            return True
        if not self.full_list_mode:
            return self._stable_count >= self.stable_cycles_to_exhaust
        if not self._saw_list_bottom:
            return False
        return self._stable_count >= self.stable_cycles_to_exhaust

    def reset(self) -> None:
        self._last_fingerprint = None
        self._stable_count = 0
        self._advance_count = 0
        self._last_tail_uid = None
        self._tail_stable_count = 0
        self._saw_list_bottom = False
        self._scroll_to_top()


# ---------------------------------------------------------------------------
# ChatFlow
# ---------------------------------------------------------------------------


class ChatFlow:
    """聊天列表回复业务装配。

    组合 ChatListUiSource + TraversalRunner，实现对聊天列表的
    不重不漏遍历回复。支持破冰消息（chat_round=0 时发消息池 1）。
    """

    def __init__(
        self,
        driver: DeviceHandler,
        elements: Dict[str, Any],
        settings: Dict[str, Any],
        pool: MessagePoolManager,
        storage: StorageHandler,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.driver = driver
        self.elements = elements or {}
        self.settings = settings or {}
        self.pool = pool
        self.storage = storage
        self.log = logger or logging.getLogger(__name__)

    # ------------------------ 内部工具 ------------------------
    def _sleep_reply_interval(self) -> None:
        ri = (self.settings.get("reply_interval") or {})
        lo = float(ri.get("min", 1.0))
        hi = float(ri.get("max", 2.0))
        time.sleep(random.uniform(lo, hi))

    def _sleep_delay(self) -> None:
        d = (self.settings.get("delay") or {})
        lo = float(d.get("min", 0.5))
        hi = float(d.get("max", 1.5))
        time.sleep(random.uniform(lo, hi))

    def _get_rid(self, *path: str) -> Optional[str]:
        node: Any = self.elements
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("resourceId")
        return None

    def _get_text(self, *path: str) -> Optional[str]:
        node: Any = self.elements
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        if isinstance(node, dict):
            return node.get("text")
        return None

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            v = (self.settings or {}).get(key)
            return int(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def _cfg_float(self, key: str, default: float) -> float:
        try:
            v = (self.settings or {}).get(key)
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    # ------------------------ 页面导航 ------------------------
    def open_chat_list(self) -> bool:
        """点击底部「消息」tab 进入聊天列表。"""
        text = self._get_text("chat_list", "chat_entry")
        if not text:
            return False
        try:
            if not self.driver.d(text=text).exists:
                self.log.info("未发现聊天入口文案: %s", text)
                return False
            ok = self.driver.random_click(text)
            if ok:
                self._sleep_delay()
                return True
            return False
        except Exception:
            self.log.exception("open_chat_list 异常")
            return False

    def _on_chat_list_screen(self) -> bool:
        """当前是否在聊天列表（非私聊内）。"""
        try:
            row_rid = self._get_rid("chat_list", "chat_row")
            if row_rid and self.driver.d(resourceId=row_rid).exists:
                return True
            input_rid = self._get_rid("buttons", "input_box")
            in_private = bool(input_rid and self.driver.d(resourceId=input_rid).exists)
            entry = self._get_text("chat_list", "chat_entry")
            if entry and self.driver.d(text=entry).exists and not in_private:
                return True
        except Exception:
            self.log.debug("_on_chat_list_screen 检测异常", exc_info=True)
        return False

    def ensure_on_chat_list(self, max_backs: int = 5) -> None:
        """离开私聊回到列表：多次 back + 校验。"""
        if self._on_chat_list_screen():
            return

        for i in range(max_backs):
            try:
                self.driver.d.press("back")
            except Exception:
                self.log.exception("press back 失败 step=%d", i)
            self._sleep_delay()
            if self._on_chat_list_screen():
                self.log.info("第 %d 次 back 后已回聊天列表", i + 1)
                return

        self.log.warning("%d 次 back 后仍不在列表，尝试 open_chat_list", max_backs)
        self.open_chat_list()

    def _open_chat_by_bounds(self, bounds: Dict[str, int]) -> bool:
        try:
            cx = (bounds["left"] + bounds["right"]) // 2
            cy = (bounds["top"] + bounds["bottom"]) // 2
            self.driver.random_click_xy(cx, cy)
            self._sleep_delay()
            return True
        except Exception:
            self.log.exception("_open_chat_by_bounds 异常")
            return False

    def _safe_back(self) -> None:
        try:
            self.driver.d.press("back")
        except Exception:
            self.log.debug("_safe_back 异常", exc_info=True)
        self._sleep_delay()

    # ------------------------ 消息发送 ------------------------
    def send_message(self, text: str) -> bool:
        """在已打开的会话中发送消息。"""
        input_rid = self._get_rid("buttons", "input_box")
        send_rid = self._get_rid("buttons", "send_button")
        if not input_rid or not send_rid:
            self.log.warning("send_message: input_box/send_button 未配置")
            return False

        try:
            if not self.driver.d(resourceId=input_rid).wait(timeout=2.0):
                self.log.warning("send_message: 输入框未出现")
                return False

            self.driver.random_click(input_rid)
            self._sleep_delay()
            self.driver.human_type(text)
            self._sleep_delay()
            self.driver.random_click(send_rid)
            self.log.info("消息已发送: %s", text)
            return True
        except Exception:
            self.log.exception("send_message 异常")
            return False

    # ------------------------ 单次回复 ------------------------
    def reply_one(self, cand: Candidate, round_: int) -> bool:
        """点开 cand 对应会话，发送消息后返回列表。

        逻辑：
        - cr=0 → 破冰（消息池 1）
        - cr 到达 huiguan_message_round → 发回关邀请话术，标记 huiguan_sent
        - huiguan_sent + 有新消息 → 仅检测互关，不回复
        - cr>=1 且有 badge → 发下一轮消息
        """
        input_rid = self._get_rid("buttons", "input_box")
        send_rid = self._get_rid("buttons", "send_button")
        if not input_rid or not send_rid:
            return False

        bounds = cand.meta.get("bounds") if isinstance(cand.meta, dict) else None
        if not isinstance(bounds, dict):
            self.log.info("reply_one: 缺 bounds uid=%s", cand.uid)
            return False

        opened = self._open_chat_by_bounds(bounds)
        if not opened:
            return False

        try:
            if not self.driver.d(resourceId=input_rid).wait(timeout=2.0):
                self.log.info("reply_one: 输入框未出现 uid=%s", cand.uid)
                self._safe_back()
                return False

            entry = self.storage.get_friend(cand.uid) or {}
            cr = int(entry.get("chat_round") or 0)
            huiguan_round = self._cfg_int("huiguan_message_round", 0)
            huiguan_text = (self.settings.get("invite_back_message") or "").strip()
            huiguan_sent = entry.get("huiguan_sent", False)

            # ---- 已发回关话术：仅检测互关，不回复 ----
            if huiguan_sent:
                self._check_mutual_only(cand, round_, input_rid, send_rid)
                return True

            # ---- 到达回关轮次 → 发回关邀请话术 ----
            if huiguan_round > 0 and cr >= huiguan_round:
                if huiguan_text:
                    if not self.send_message(huiguan_text):
                        return False
                    self.log.info("reply_one: 已发回关话术 → %s", cand.name or cand.uid)
                self.storage.upsert(cand.uid, {"huiguan_sent": True})
                self._check_mutual_only(cand, round_, input_rid, send_rid)
                return True

            # ---- 正常消息 ----
            if cr == 0:
                msg = self.pool.get_message_for_round(1)
            else:
                msg = self.pool.get_message_for_round(cr + 1)

            if not msg:
                self.log.warning("reply_one: 无可用消息 uid=%s", cand.uid)
                return False

            if not self.send_message(msg):
                return False

            self.storage.increment_chat_round(cand.uid)

            entry_status = entry.get("status", "accepted")
            if entry_status in ("failed",):
                entry_status = "accepted"
            if cand.name and entry.get("name") != cand.name:
                self.storage.mark_status(cand.uid, entry_status, name=cand.name)
            else:
                self.storage.mark_status(cand.uid, entry_status)

            self.log.info("reply_one: 已回复 %s: %s (cr=%d)", cand.name or cand.uid, msg, cr)
            return True
        except Exception:
            self.log.exception("reply_one 异常 uid=%s", cand.uid)
            return False
        finally:
            self._safe_back()

    def _check_mutual_only(self, cand: Candidate, round_: int,
                           input_rid: str, send_rid: str) -> None:
        """仅检测互关状态（不发送消息），用于回关话术发送后的阶段。"""
        try:
            from actions.mutual_friend import detect_mutual_friend_by_voice_button
            result = detect_mutual_friend_by_voice_button(
                self.driver, self.elements, restore_text_mode=True
            )
            if result and result.get("status") == "mutual":
                self.storage.mark_status(cand.uid, "mutual", name=cand.name)
                self.log.info("_check_mutual_only: %s 已是互关", cand.name or cand.uid)
            else:
                self.log.info("_check_mutual_only: %s 尚未互关", cand.name or cand.uid)
        except Exception:
            self.log.exception("_check_mutual_only 异常 uid=%s", cand.uid)

    # ------------------------ 遍历回复入口 ------------------------
    def reply_all_new(
        self,
        round_: int,
        *,
        gate: Optional[Callable[[], None]] = None,
        max_actions: Optional[int] = None,
        full_list_mode: Optional[bool] = None,
    ) -> TraversalReport:
        """扫聊天列表，给每个「待处理」的好友各回一次。

        使用 TraversalRunner + ChatListUiSource 实现不重不漏遍历。
        """
        settings = self.settings or {}

        # 引擎参数
        flm = full_list_mode if full_list_mode is not None else True
        madv = self._cfg_int("chat_list_max_advance", 64)
        cyc = self._cfg_int("chat_list_stable_cycles", 2)
        sr = self._cfg_float("chat_list_scroll_ratio", 0.75)
        bsc = self._cfg_int("chat_list_bottom_stable_cycles", 2)
        sdm = self._cfg_int("chat_list_settle_delay_ms", 350)
        no_adv = self._cfg_int("traversal_max_no_advance_cycles", 2)

        ignore_names = list(settings.get("chat_ignore_names") or [])
        # 动态添加目标群名（群聊不是好友，不应回复）
        group_name = (settings.get("group_name") or "").strip()
        if group_name:
            ignore_names.append(group_name)

        def _already_done(uid: str) -> bool:
            """判断好友是否本轮已完成（无需再处理）。"""
            _, entry = self.storage.resolve_friend(uid)
            if entry is None:
                return True
            cr = int(entry.get("chat_round") or 0)
            S = self._cfg_int("max_chat_rounds", 10)
            status = entry.get("status") or ""
            if status == "done":
                return True
            # 已发送回关话术 → 不再回复，仅检测互关
            if entry.get("huiguan_sent"):
                return True
            # cr=0 → 需要破冰
            if cr == 0:
                return False
            # cr>=S → 本轮不再回复
            if cr >= S:
                return True
            return False

        def _visible_extra_filter(cand: Candidate) -> bool:
            """破冰后只回复有新消息的好友；已发回关话术的仅检测互关不回复。"""
            _, entry = self.storage.resolve_friend(cand.uid, cand.name)
            if entry is None:
                return False
            cr = int(entry.get("chat_round") or 0)
            # 已发回关话术 → 有新消息才进入（仅检测互关，不回复）
            if entry.get("huiguan_sent"):
                return bool(cand.meta.get("has_unread"))
            # cr=0 → 始终可见（需要破冰）
            if cr == 0:
                return True
            # cr>=1 → 只有对方发了新消息（有 badge）才可见
            return bool(cand.meta.get("has_unread"))

        def _mark_done(cand: Candidate, ok: bool) -> None:
            if not ok:
                try:
                    self.storage.mark_status(cand.uid, "failed", name=cand.name)
                except Exception:
                    self.log.exception("mark failed 异常 uid=%s", cand.uid)

        source = ChatListUiSource(
            self.driver,
            self.elements,
            already_done=_already_done,
            full_list_mode=flm,
            scroll_to_top=lambda: self.open_chat_list(),
            stable_cycles_to_exhaust=cyc,
            max_advance=madv,
            scroll_ratio=sr,
            bottom_stable_cycles=bsc,
            settle_delay_ms=sdm,
            ignore_names=ignore_names,
            recover_to_chat_list=lambda: self.ensure_on_chat_list(),
            visible_extra_filter=_visible_extra_filter,
            logger=self.log,
        )

        runner = TraversalRunner(
            source=source,
            action=lambda c: self.reply_one(c, round_),
            round_id=round_,
            already_done=_already_done,
            mark_done=_mark_done,
            gate=gate or (lambda: None),
            max_actions=max_actions,
            max_no_advance_cycles=max(1, no_adv),
            logger=self.log,
        )
        return runner.run()

    # ------------------------ 招呼处理 ------------------------
    def scan_and_enter_sayhi_list(self) -> bool:
        """扫描「收到的招呼」角标并进入招呼列表。"""
        from core.greeter import GreetingScanner
        greeter = GreetingScanner(self.driver, self.elements, self.settings)
        badge = greeter.scan_badge()
        if badge <= 0:
            self.log.debug("无新招呼")
            return False
        self.log.info("发现 %d 个新招呼", badge)
        return greeter.enter_sayhi_list()

    def approve_sayhi_one(self) -> Optional[Dict[str, Any]]:
        """通过一个招呼。返回 {"name": str} 或 None。"""
        from core.greeter import GreetingScanner
        greeter = GreetingScanner(self.driver, self.elements, self.settings)
        return greeter.approve_one()

    def go_back_to_chat_list_from_sayhi(self) -> bool:
        """从招呼列表返回主聊天列表。"""
        from core.greeter import GreetingScanner
        greeter = GreetingScanner(self.driver, self.elements, self.settings)
        return greeter.go_back_to_chat_list()


"""按轮次批量处理好友会话。

每轮三个阶段：
  Step A — 通过新招呼（只点按钮，不发消息）
  Step B — 聊天列表统一扫描 + 处理（cr=0 发破冰，有未读发回复）
  Phase 3 — 关注 + 互关检测 + 邀请进群 + 拉黑
  Phase 4 — 等待下一轮
"""

import logging
import random
import time
import xml.etree.ElementTree as ET
from typing import Optional

from actions.chat_topbar import handle_chat_topbar_friend_actions
from actions.mutual_friend import detect_mutual_friend_by_voice_button
from core.chatter import OneOnOneChatter
from core.driver import DeviceHandler
from core.greeter import GreetingScanner
from core.group_invite import GroupInviter
from core.message_pool import MessagePoolManager
from data.storage import StorageHandler
from utils.helpers import parse_bounds, random_delay


# ---------------------------------------------------------------------------
# 状态标签（仅用于日志，不再驱动状态机）
# ---------------------------------------------------------------------------

class Phase:
    """好友管线阶段标签（纯日志用途）。"""
    IDLE = "IDLE"
    APPROVING = "APPROVING"
    SCANNING = "SCANNING"
    CHATTING = "CHATTING"
    CLICKING_FOLLOW = "CLICKING_FOLLOW"
    CHECKING_MUTUAL = "CHECKING_MUTUAL"
    INVITING_TO_GROUP = "INVITING_TO_GROUP"
    DONE = "DONE"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# SessionRound — 按轮次批量执行
# ---------------------------------------------------------------------------

class SessionRound:
    """按轮次批量管理所有好友会话。每轮 execute() 执行四个阶段。"""

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

        self.greeter = GreetingScanner(driver, elements, settings)
        self.chatter = OneOnOneChatter(driver, elements, settings, storage)
        self.inviter = GroupInviter(driver, elements, settings)

        try:
            self._pool = MessagePoolManager(settings, state_path="data/state.json")
        except Exception:
            logging.exception("SessionRound 消息池初始化失败")
            self._pool = None

        # 配置参数
        self.N: int = max(1, int(settings.get("chat_rounds_before_follow", 3)))
        self.S: int = max(1, int(settings.get("max_chat_rounds", 10)))
        self.round_end_wait: float = float(settings.get("round_end_wait_s", 10))

        # 运行时状态
        self.round_number: int = 0
        self.current_phase: str = Phase.IDLE
        self.friends_processed_this_round: int = 0

        self._logger = logging.getLogger("session")

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def execute_one_round(self) -> None:
        """执行一整轮：Step A → Step B → Phase 3 → Phase 4。"""
        self.round_number += 1
        self.friends_processed_this_round = 0

        self._logger.info("=" * 40)
        self._logger.info("第 %d 轮开始", self.round_number)
        self._logger.info("=" * 40)

        try:
            self._step_approve_greetings()
        except Exception:
            self._logger.exception("Step A 异常，继续 Step B")

        try:
            self._step_scan_and_process()
        except Exception:
            self._logger.exception("Step B 异常，继续 Phase 3")

        try:
            self._phase3_follow_and_mutual()
        except Exception:
            self._logger.exception("Phase 3 异常，继续 Phase 4")

        self._phase4_wait()

        self._logger.info(
            "第 %d 轮结束，本轮处理 %d 个好友",
            self.round_number,
            self.friends_processed_this_round,
        )

    # ------------------------------------------------------------------
    # Step A — 通过新招呼（只点按钮，入库 cr=0，不发消息）
    # ------------------------------------------------------------------

    def _step_approve_greetings(self) -> None:
        """在招呼列表中逐个点击「通过」，收集昵称并入库 cr=0。

        不发消息，消息的发送统一在 Step B 的聊天列表扫描中完成。
        """
        self.current_phase = Phase.APPROVING

        badge = self.greeter.scan_badge()
        if badge <= 0:
            self._logger.debug("Step A: 无新招呼")
            return

        self._logger.info("Step A: 发现 %d 个新招呼", badge)

        if not self.greeter.enter_sayhi_list():
            self._logger.warning("Step A: 进入招呼列表失败")
            return

        time.sleep(0.8)
        approved_count = 0

        while True:
            result = self.greeter.approve_one()
            if result is None:
                self._logger.info("Step A: 无更多「通过」按钮")
                break

            name = result.get("name") or "unknown"
            # 入库 cr=0，不区分名字是否识别到
            self.storage.mark_status(name, "accepted", chat_round=0, name=name)
            approved_count += 1
            self._logger.info("Step A: 已通过 %s", name)

        self.greeter.go_back_to_chat_list()
        self._logger.info("Step A: 完成，通过 %d 人", approved_count)

    # ------------------------------------------------------------------
    # Step B — 聊天列表统一扫描 + 处理
    # ------------------------------------------------------------------

    def _step_scan_and_process(self) -> None:
        """从聊天列表顶部开始，逐屏扫描并当场处理每个需要操作的好友。

        处理逻辑：
          - cr=0 → 发破冰（池 1），cr→1
          - cr>=1 且有未读角标 → 发下一条（池 cr+1），cr+1
          - status=done → 跳过

        看到就处理，处理完退出对话框后继续往下翻。
        seen_names 防止同一轮内重复处理同一个人。
        """
        self.current_phase = Phase.SCANNING

        row_rid = self.chatter._get_rid("chat_list", "chat_row")
        name_rid = self.chatter._get_rid("chat_list", "chat_row_name")
        unread_rid = self.chatter._get_rid("chat_list", "chat_unread_badge")
        ignore_names = set(self.settings.get("chat_ignore_names") or [])

        if not row_rid:
            self._logger.warning("Step B: 未配置 chat_row resourceId")
            return

        all_friends = self.storage.get_all_friends()
        if not all_friends:
            self._logger.debug("Step B: friends.json 为空")
            return

        seen_names: set = set()
        processed = 0

        # 点击「消息」tab 回到列表顶部
        self._scroll_to_top_of_chat_list()

        for scroll in range(10):
            try:
                xml = self.driver.d.dump_hierarchy()
            except Exception:
                self._logger.debug("Step B: dump hierarchy 异常 scroll=%d", scroll)
                time.sleep(0.5)
                continue

            root = ET.fromstring(xml)
            found_any_row = False

            for node in root.iter():
                if node.attrib.get("resource-id") != row_rid:
                    continue

                found_any_row = True

                row_name = ""
                has_badge = False
                for child in node.iter():
                    rid = child.attrib.get("resource-id", "")
                    if rid == unread_rid:
                        has_badge = True
                    elif rid == name_rid:
                        row_name = (child.attrib.get("text") or "").strip()

                if not row_name or row_name in ignore_names:
                    continue
                if row_name in seen_names:
                    continue

                # 模糊匹配 friends.json 中的好友
                matched = self._match_friend(all_friends, row_name)
                if matched is None:
                    continue

                uid = matched["uid"]
                fname = matched["name"]
                status = matched.get("status") or "accepted"
                cr = int(matched.get("chat_round") or 0)

                # ---- 决定动作 ----
                if status == "done":
                    continue

                if cr == 0:
                    # 新通过的好友，发破冰
                    action = "icebreaker"
                elif has_badge and cr < self.S:
                    # 有未读消息，发跟进
                    action = "reply"
                else:
                    continue

                # ---- 执行 ----
                seen_names.add(row_name)
                self._logger.info(
                    "Step B: %s → %s (cr=%d)", row_name, action, cr
                )

                if not self.chatter.find_and_enter_chat(fname):
                    self._logger.warning("Step B: 进入 %s 对话框失败", fname)
                    continue

                ok = False
                if action == "icebreaker" and self._pool:
                    msg = self._pool.get_message_for_round(1)
                    ok = self.chatter.send_message(msg)
                    if ok:
                        self.storage.increment_chat_round(uid)
                        processed += 1
                        self._logger.info("Step B: 破冰已发送 → %s", fname)
                elif action == "reply" and self._pool:
                    pool_index = cr + 1
                    msg = self._pool.get_message_for_round(pool_index)
                    ok = self.chatter.send_message(msg)
                    if ok:
                        self.storage.increment_chat_round(uid)
                        processed += 1
                        self._logger.info(
                            "Step B: 池%d 已发送 → %s", pool_index, fname
                        )

                if not ok:
                    self._logger.warning("Step B: 消息发送失败 → %s", fname)

                # 退出对话框，继续扫描
                self.chatter.go_back_to_chat_list()
                random_delay(self.settings)

            # 当前屏没有找到任何聊天行（已滑到底），提前退出
            if not found_any_row and scroll > 0:
                self._logger.debug("Step B: scroll=%d 无聊天行，停止翻屏", scroll)
                break

            # 下翻
            if scroll < 9:
                try:
                    self.driver.swipe_scroll_down()
                except Exception:
                    self._logger.debug("Step B: 滚动异常", exc_info=True)
                time.sleep(random.uniform(0.3, 0.6))

        self.friends_processed_this_round += processed
        self._logger.info("Step B: 完成，处理了 %d 个好友", processed)

    # ------------------------------------------------------------------
    # Step B 辅助方法
    # ------------------------------------------------------------------

    def _scroll_to_top_of_chat_list(self) -> None:
        """点击底部「消息」tab 使聊天列表回到顶部。"""
        chat_entry_text = self.chatter._get_text("chat_list", "chat_entry")
        if not chat_entry_text:
            return
        try:
            xml = self.driver.d.dump_hierarchy()
            root = ET.fromstring(xml)
            for node in root.iter():
                if (node.attrib.get("text") or "").strip() == chat_entry_text:
                    b = parse_bounds(node.attrib.get("bounds", ""))
                    if b:
                        cx = (b[0] + b[2]) // 2
                        cy = (b[1] + b[3]) // 2
                        self.driver.random_click_xy(cx, cy)
                        time.sleep(random.uniform(0.3, 0.6))
                        return
        except Exception:
            self._logger.debug("Step B: 回到顶部失败", exc_info=True)

    def _match_friend(self, all_friends: dict, row_name: str) -> Optional[dict]:
        """在 friends.json 中模糊匹配聊天列表行名。返回含 uid/name 的 dict 或 None。"""
        for uid, friend in all_friends.items():
            fname = friend.get("name") or uid
            if fname in row_name:
                return {"uid": uid, "name": fname, **friend}
        return None

    # ------------------------------------------------------------------
    # Phase 3 — 关注 + 互关检测 + 邀请 + 拉黑
    # ------------------------------------------------------------------

    def _phase3_follow_and_mutual(self) -> None:
        """遍历 friends.json：
          - chat_round >= N 且 status=="accepted" → 点关注
          - status=="followed" → 检测互关 → 互关则邀请进群 + 拉黑 → done
        """
        self.current_phase = Phase.CHECKING_MUTUAL

        all_friends = self.storage.get_all_friends()
        if not all_friends:
            return

        self._logger.info("Phase 3: 检查 %d 个好友的关注/互关状态", len(all_friends))

        for uid, friend in all_friends.items():
            try:
                status = friend.get("status") or "accepted"
                if status == "done":
                    continue

                chat_round = int(friend.get("chat_round") or 0)
                name = friend.get("name") or uid

                if status == "accepted" and chat_round >= self.N:
                    self._do_follow(uid, name, chat_round)
                elif status == "followed":
                    self._do_mutual_check(uid, name)

            except Exception:
                self._logger.exception("Phase 3: 处理 %s 失败", uid)
                try:
                    self.chatter.go_back_to_chat_list()
                except Exception:
                    pass

    def _do_follow(self, uid: str, name: str, chat_round: int) -> None:
        """进对话框，利用 chat_topbar 点关注按钮。"""
        self.current_phase = Phase.CLICKING_FOLLOW
        self._logger.info(
            "Phase 3: %s 已聊 %d 轮（>=%d），点关注", name, chat_round, self.N
        )

        if not self.chatter.find_and_enter_chat(name):
            self._logger.warning("Phase 3: 进入 %s 对话框失败", name)
            return

        handle_chat_topbar_friend_actions(
            self.driver,
            self.elements,
            self.storage,
            uid=uid,
            name=name,
            round_id=chat_round,
        )

        self.storage.mark_status(uid, "followed", name=name)
        self._logger.info("Phase 3: %s 已关注 -> followed", name)
        self.chatter.go_back_to_chat_list()

    def _do_mutual_check(self, uid: str, name: str) -> None:
        """进对话框检测互关状态；互关则邀请进群 + 拉黑 → done。"""
        self.current_phase = Phase.CHECKING_MUTUAL
        self._logger.info("Phase 3: 检测 %s 互关状态", name)

        if not self.chatter.find_and_enter_chat(name):
            self._logger.warning("Phase 3: 进入 %s 对话框失败", name)
            return

        result = detect_mutual_friend_by_voice_button(
            self.driver, self.elements, restore_text_mode=True
        )

        if result.is_mutual:
            self.current_phase = Phase.INVITING_TO_GROUP
            self._logger.info("Phase 3: %s 已是互关好友，邀请进群", name)

            # 先回到聊天列表
            self.inviter.go_back_to_chat_list()

            group_name = self.settings.get("group_name", "")
            if group_name:
                if self.inviter.enter_group_info_directly(group_name):
                    if self.inviter.open_invite_panel():
                        if self.inviter.select_friend(name):
                            self.inviter.confirm_invite()
                        else:
                            self._logger.warning("未在邀请面板找到 %s", name)
                    else:
                        self._logger.warning("无法打开邀请面板")
                else:
                    self._logger.warning("无法进入群信息页「%s」", group_name)
                self.inviter.go_back_to_chat_list()

            # 拉黑
            self.inviter.block_friend(name)

            self.storage.mark_status(uid, "done", name=name)
            self._logger.info("Phase 3: %s 已完成（邀请+拉黑）", name)
        else:
            self._logger.info(
                "Phase 3: %s 尚未互关 (%s)，下轮再检", name, result.reason
            )
            self.chatter.go_back_to_chat_list()

    # ------------------------------------------------------------------
    # Phase 4 — 等待下一轮
    # ------------------------------------------------------------------

    def _phase4_wait(self) -> None:
        """本轮结束，等待 round_end_wait_s 秒后进入下一轮。"""
        self.current_phase = Phase.IDLE
        self._logger.debug(
            "Phase 4: 等待 %.0f 秒后进入下一轮", self.round_end_wait
        )
        time.sleep(self.round_end_wait)

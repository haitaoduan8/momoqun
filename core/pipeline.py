"""按轮次批量处理好友会话。

每轮四个阶段：
  Phase 1 — 通过新招呼 + 发破冰消息
  Phase 2 — 回复已有好友的未读消息
  Phase 3 — 关注 + 互关检测 + 邀请进群 + 拉黑
  Phase 4 — 等待下一轮
"""

import logging
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
from utils.helpers import random_delay


# ---------------------------------------------------------------------------
# 状态标签（仅用于日志，不再驱动状态机）
# ---------------------------------------------------------------------------

class Phase:
    """好友管线阶段标签（纯日志用途）。"""
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    ENTERING_SAYHI = "ENTERING_SAYHI"
    APPROVING = "APPROVING"
    ENTERING_CHAT = "ENTERING_CHAT"
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
        """执行一整轮会话：Phase 1 → Phase 2 → Phase 3 → Phase 4。"""
        self.round_number += 1
        self.friends_processed_this_round = 0

        self._logger.info("=" * 40)
        self._logger.info("第 %d 轮开始", self.round_number)
        self._logger.info("=" * 40)

        try:
            self._phase1_approve_new()
        except Exception:
            self._logger.exception("Phase 1 异常，继续 Phase 2")

        try:
            self._phase2_reply_unread()
        except Exception:
            self._logger.exception("Phase 2 异常，继续 Phase 3")

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
    # Phase 1 — 通过新招呼 + 发破冰消息
    # ------------------------------------------------------------------

    def _phase1_approve_new(self) -> None:
        """通过所有新招呼，每个新好友发破冰消息（池 1）。

        Phase 1 新通过的好友 chat_round=0，本轮 Phase 2 不再回复。
        """
        self.current_phase = Phase.APPROVING

        badge = self.greeter.scan_badge()
        if badge <= 0:
            self._logger.debug("Phase 1: 无新招呼")
            return

        self._logger.info("Phase 1: 发现 %d 个新招呼", badge)

        if not self.greeter.enter_sayhi_list():
            self._logger.warning("Phase 1: 进入招呼列表失败")
            return

        time.sleep(0.8)
        approved_count = 0

        while True:
            result = self.greeter.approve_one()
            if result is None:
                self._logger.info("Phase 1: 无更多「通过」按钮")
                break

            name = result.get("name") or "unknown"
            self._logger.info("Phase 1: 已通过招呼 %s", name)

            # 入库：status=accepted，chat_round=0 标记本轮新通过
            self.storage.mark_status(name, "accepted", chat_round=0, name=name)

            # 等对话框打开（雷电等模拟器跳转慢，之前 1-2 秒不够）
            input_rid = self.chatter._get_rid("buttons", "input_box")
            dialog_ready = False
            if input_rid:
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    try:
                        el = self.driver.d(resourceId=input_rid)
                        if el.exists:
                            dialog_ready = True
                            break
                    except Exception:
                        pass
                    time.sleep(0.5)

            if not dialog_ready:
                self._logger.warning("Phase 1: 对话框未打开，跳过发消息 -> %s", name)
                self.greeter.go_back_to_chat_list()
                approved_count += 1
                if not self.greeter.enter_sayhi_list():
                    break
                time.sleep(0.8)
                continue

            # 发破冰消息（消息池第 1 池）
            if self._pool:
                icebreaker = self._pool.get_message_for_round(1)
                self._logger.info("Phase 1: 发送破冰消息 -> %s", name)
                ok = self.chatter.send_message(icebreaker)
                if not ok:
                    self._logger.warning("Phase 1: 破冰消息发送失败 -> %s", name)
                random_delay(self.settings)

            approved_count += 1

            # 回到聊天列表，再进招呼列表看还有没有
            self.greeter.go_back_to_chat_list()
            if not self.greeter.enter_sayhi_list():
                self._logger.warning("Phase 1: 重新进入招呼列表失败")
                break
            time.sleep(0.8)

        self.greeter.go_back_to_chat_list()
        self._logger.info("Phase 1: 完成，通过 %d 人", approved_count)

    # ------------------------------------------------------------------
    # Phase 2 — 回复有未读消息的好友
    # ------------------------------------------------------------------

    def _phase2_reply_unread(self) -> None:
        """回复有未读消息且在 friends.json 中的好友。

        跳过 chat_round==0 的（本轮 Phase 1 刚通过的）以及 over limit 的。
        """
        self.current_phase = Phase.CHATTING

        unread_queue = self._collect_unread_friends()
        if not unread_queue:
            self._logger.debug("Phase 2: 无待回复好友")
            return

        self._logger.info("Phase 2: 发现 %d 个有未读消息的好友", len(unread_queue))

        for friend in unread_queue:
            try:
                self._process_one_reply(friend)
                self.friends_processed_this_round += 1
            except Exception:
                self._logger.exception("Phase 2: 回复 %s 失败", friend["name"])
                try:
                    self.chatter.go_back_to_chat_list()
                except Exception:
                    pass

        self._logger.info(
            "Phase 2: 完成，处理了 %d 个好友", self.friends_processed_this_round
        )

    def _collect_unread_friends(self) -> list:
        """Dump 聊天列表 hierarchy，收集所有有 unread_badge 且在 friends.json 中的好友。

        按名字模糊匹配；跳过：
          - chat_round == 0（本轮 Phase 1 新通过）
          - chat_round >= S（超过最大轮数）
          - status in (done, failed)
        """
        try:
            xml = self.driver.d.dump_hierarchy()
        except Exception:
            self._logger.warning("Phase 2: dump hierarchy 失败")
            return []

        root = ET.fromstring(xml)
        row_rid = self.chatter._get_rid("chat_list", "chat_row")
        name_rid = self.chatter._get_rid("chat_list", "chat_row_name")
        unread_rid = self.chatter._get_rid("chat_list", "chat_unread_badge")
        ignore_names = set(self.settings.get("chat_ignore_names") or [])

        if not row_rid:
            return []

        all_friends = self.storage.get_all_friends()
        unread_queue: list = []

        for node in root.iter():
            if node.attrib.get("resource-id") != row_rid:
                continue

            row_name = ""
            has_badge = False
            for child in node.iter():
                rid = child.attrib.get("resource-id", "")
                if rid == unread_rid:
                    has_badge = True
                elif rid == name_rid:
                    row_name = (child.attrib.get("text") or "").strip()

            if not has_badge or not row_name:
                continue
            if row_name in ignore_names:
                continue

            # 模糊匹配 friends.json 中的好友
            for uid, friend in all_friends.items():
                fname = friend.get("name") or uid
                if fname not in row_name:
                    continue

                chat_round = int(friend.get("chat_round") or 0)
                status = friend.get("status") or "accepted"

                if status in ("done", "failed"):
                    continue
                if chat_round == 0:   # 本轮 Phase 1 新通过
                    continue
                if chat_round >= self.S:
                    continue

                unread_queue.append({
                    "uid": uid,
                    "name": fname,
                    "chat_round": chat_round,
                })
                break

        return unread_queue

    def _process_one_reply(self, friend: dict) -> None:
        """对单个好友：进对话框 → 发消息 → chat_round+1 → back。"""
        name = friend["name"]
        uid = friend["uid"]
        chat_round = friend["chat_round"]

        self._logger.info("Phase 2: 回复 %s (chat_round=%d)", name, chat_round)

        if not self.chatter.find_and_enter_chat(name):
            self._logger.warning("Phase 2: 进入 %s 对话框失败", name)
            return

        # 消息池索引：chat_round + 1（破冰是池 1，第 1 次回复是池 2）
        pool_index = chat_round + 1
        sent = False
        if self._pool:
            msg = self._pool.get_message_for_round(pool_index)
            self._logger.info("Phase 2: 发送池 %d -> %s", pool_index, name)
            sent = self.chatter.send_message(msg)

        if not sent and self._pool:
            self._logger.warning("Phase 2: 消息发送失败，不增加轮次 -> %s", name)
            return

        # 写入 friends.json
        self.storage.increment_chat_round(uid)
        random_delay(self.settings)
        self.chatter.go_back_to_chat_list()

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

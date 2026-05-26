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

        # 保留 greeter 用于招呼处理（Phase 1）
        self.greeter = GreetingScanner(driver, elements, settings)
        # 保留 chatter 用于 _scroll_to_top 等辅助方法
        self.chatter = OneOnOneChatter(driver, elements, settings, storage)
        self.inviter = GroupInviter(driver, elements, settings)

        try:
            self._pool = MessagePoolManager(settings, state_path="data/state.json")
        except Exception:
            logging.exception("SessionRound 消息池初始化失败")
            self._pool = None

        # 初始化 ChatFlow（遍历式回复引擎）
        from core.chat_flow import ChatFlow
        self.chat_flow = ChatFlow(
            driver=driver,
            elements=elements,
            settings=settings,
            pool=self._pool,
            storage=storage,
        )

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
        direct_mode = self.settings.get("direct_group_mode", False)

        self._logger.info("=" * 40)
        self._logger.info("第 %d 轮开始%s", self.round_number,
                          " [直接拉群模式]" if direct_mode else "")
        self._logger.info("=" * 40)

        try:
            self._step_approve_greetings()
        except Exception:
            self._logger.exception("Step A 异常，继续 Step B")

        if not direct_mode:
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

        back_ok = self.greeter.go_back_to_chat_list()
        if not back_ok:
            self._logger.warning("Step A: go_back_to_chat_list 返回失败，尝试额外恢复")
            try:
                self.driver.d.press("back")
                time.sleep(random.uniform(0.5, 1.0))
                self.driver.wait_ui_stable(max_wait=1.0)
            except Exception:
                self._logger.debug("Step A: 额外 back 恢复异常", exc_info=True)

        # 防御性验证：确认不在招呼子页面
        accept_rid = self.greeter._get_rid("buttons", "accept_button")
        row_rid = self.greeter._get_rid("chat_list", "chat_row")
        try:
            xml = self.driver.d.dump_hierarchy()
            if accept_rid and accept_rid in xml:
                self._logger.error(
                    "Step A: 恢复后仍在招呼子页面（检测到 accept_button），"
                    "Step B 可能扫描异常"
                )
            elif row_rid and row_rid in xml:
                self._logger.info("Step A: 已验证回到主聊天列表")
            else:
                self._logger.warning(
                    "Step A: 无法确认当前页面状态（无 chat_row 无 accept_button）"
                )
        except Exception:
            self._logger.debug("Step A: 页面验证异常", exc_info=True)

        self._logger.info("Step A: 完成，通过 %d 人", approved_count)

    # ------------------------------------------------------------------
    # Step B — 聊天列表统一扫描 + 处理
    # ------------------------------------------------------------------

    def _step_scan_and_process(self) -> None:
        """使用 TraversalRunner + ChatListUiSource 遍历聊天列表，
        对每个待处理的好友执行回复（破冰/跟进）。

        基于 Momo_Project 的不重不漏遍历架构重写。
        """
        self.current_phase = Phase.SCANNING

        all_friends = self.storage.get_all_friends()
        self._logger.info(
            "Step B: friends.json 共 %d 个好友: %s",
            len(all_friends or {}),
            [(f.get("name", uid), f.get("chat_round", "?"), f.get("status", "?"))
             for uid, f in (all_friends or {}).items()],
        )

        if not self.chat_flow.open_chat_list():
            self._logger.warning("Step B: 进入聊天列表失败")
            return

        report = self.chat_flow.reply_all_new(
            round_=self.round_number,
            gate=None,
        )

        self.friends_processed_this_round += len(report.processed)
        self._logger.info(
            "Step B: 完成，处理 %d 人，跳过已done %d，失败 %d，原因=%s",
            len(report.processed),
            report.skipped_already_done,
            len(report.failed),
            report.stopped_reason,
        )

    # ------------------------------------------------------------------
    # Phase 3 — 关注 + 互关检测 + 邀请 + 拉黑
    # ------------------------------------------------------------------

    def _phase3_follow_and_mutual(self) -> None:
        """遍历 friends.json：
          - 直接拉群模式：status=="accepted" → 立即关注+邀请+拉黑
          - 普通模式：chat_round >= N 且 status=="accepted" → 点关注
          - status=="followed" → 检测互关 → 互关则邀请进群 + 拉黑 → done
        """
        self.current_phase = Phase.CHECKING_MUTUAL
        direct_mode = self.settings.get("direct_group_mode", False)

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

                # 直接拉群模式：跳过聊天，直接关注+检测互关
                if direct_mode and status in ("accepted",):
                    self._logger.info("Phase 3: %s 直接拉群模式 → 点关注", name)
                    self._do_follow(uid, name, chat_round)
                    # 关注后立即检测互关
                    self._do_mutual_check(uid, name)
                elif not direct_mode and status == "accepted" and chat_round >= self.N:
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

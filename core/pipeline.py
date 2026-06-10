"""按轮次批量处理好友会话。

每轮三个阶段：
  Step A — 通过新招呼（只点按钮，不发消息）
  Step B — 邀请进群（回到消息页继续监测招呼）
  Phase 4 — 等待下一轮
"""

import logging
import time
from typing import Optional

from core.driver import DeviceHandler
from core.greeter import GreetingScanner
from core.group_invite import GroupInviter
from data.storage import StorageHandler
from actions.ui_hierarchy import DumpRecoveryFailed
from utils.helpers import ensure_on_chat_list


class Phase:
    """好友管线阶段标签（纯日志用途）。"""
    IDLE = "IDLE"
    APPROVING = "APPROVING"
    INVITING_TO_GROUP = "INVITING_TO_GROUP"
    DONE = "DONE"
    ERROR = "ERROR"


class SessionRound:
    """按轮次批量管理所有好友会话。每轮 execute() 执行三个阶段。"""

    def __init__(
        self,
        driver: DeviceHandler,
        elements: dict,
        settings: dict,
        storage: StorageHandler,
        serial: Optional[str] = None,
    ) -> None:
        self.driver = driver
        self.elements = elements
        self.settings = settings
        self.storage = storage
        self.serial: Optional[str] = serial or getattr(storage, "serial", None)

        self.greeter = GreetingScanner(
            driver, elements, settings, serial=self.serial
        )
        self.inviter = GroupInviter(
            driver, elements, settings, serial=self.serial
        )

        self.round_end_wait: float = float(settings.get("round_end_wait_s", 10))

        self.round_number: int = 0
        self.current_phase: str = Phase.IDLE
        self.friends_processed_this_round: int = 0
        self.last_approved_count: int = 0
        self._approved_this_round: list[tuple[str, str]] = []

        self._logger = logging.getLogger(
            f"session.{self.serial}" if self.serial else "session"
        )

    def apply_config(self, settings: dict, elements: dict) -> None:
        """热更新配置：同步到子模块。"""
        self.settings = settings or {}
        self.elements = elements or {}
        self.round_end_wait = float(self.settings.get("round_end_wait_s", 10))
        for comp in (self.greeter, self.inviter):
            comp.settings = self.settings
            comp.elements = self.elements

    def execute_one_round(self) -> None:
        """执行一整轮：Step A → Step B → Phase 4。"""
        self.round_number += 1
        self.friends_processed_this_round = 0
        self.last_approved_count = 0

        self._logger.info("=" * 40)
        self._logger.info("第 %d 轮开始", self.round_number)
        self._logger.info("=" * 40)

        try:
            self._step_approve_greetings()
        except DumpRecoveryFailed:
            raise
        except Exception:
            self._logger.exception("Step A 异常，继续 Step B")

        try:
            self._step_invite_to_group()
        except DumpRecoveryFailed:
            raise
        except Exception:
            self._logger.exception("Step B 异常，继续 Phase 4")

        self._phase4_wait()

        self._logger.info(
            "第 %d 轮结束，本轮处理 %d 个好友",
            self.round_number,
            self.friends_processed_this_round,
        )

    def _first_batch_min_count(self) -> int:
        cfg = (self.settings or {}).get("approve_greeting") or {}
        try:
            return max(0, int(cfg.get("first_batch_min_count", 3)))
        except (TypeError, ValueError):
            return 3

    def _first_greet_batch_done(self) -> bool:
        return self.storage.get_device_state_flag("first_greet_batch_done", False)

    def _step_approve_greetings(self) -> None:
        """在招呼列表中逐个点击「通过」，收集昵称并入库。"""
        self.current_phase = Phase.APPROVING
        self._approved_this_round = []

        try:
            ensure_on_chat_list(
                self.driver,
                self.elements,
                logger=self._logger,
                serial=self.serial,
            )
        except DumpRecoveryFailed:
            raise
        except Exception:
            self._logger.exception("Step A: 归位聊天列表失败")

        badge = self.greeter.scan_badge()
        if badge <= 0:
            self._logger.debug("Step A: 无新招呼")
            return

        if not self._first_greet_batch_done():
            min_count = self._first_batch_min_count()
            if badge < min_count:
                self._logger.info(
                    "Step A: 首批招呼 %d 未达阈值 %d，跳过",
                    badge,
                    min_count,
                )
                return
        else:
            self._logger.info("Step A: 后续批次，招呼数 %d（无需阈值）", badge)

        self._logger.info("Step A: 发现 %d 个新招呼，开始通过", badge)

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
            uid = name if name != "unknown" else f"unknown_{approved_count}"
            self.storage.mark_status(uid, "accepted", chat_round=0, name=name)
            self._approved_this_round.append((uid, name))
            approved_count += 1
            self._logger.info("Step A: 已通过 %s", name)

        back_ok = self.greeter.go_back_to_chat_list()
        if not back_ok:
            self._logger.warning(
                "Step A: go_back_to_chat_list 返回失败，尝试 ensure_on_chat_list"
            )
            try:
                ensure_on_chat_list(
                    self.driver,
                    self.elements,
                    logger=self._logger,
                    serial=self.serial,
                )
            except DumpRecoveryFailed:
                raise
            except Exception:
                self._logger.exception("Step A: ensure_on_chat_list 恢复失败")

        accept_rid = self.greeter._get_rid("buttons", "accept_button")
        row_rid = self.greeter._get_rid("chat_list", "chat_row")
        try:
            xml = self.driver.d.dump_hierarchy()
            if accept_rid and accept_rid in xml:
                self._logger.error(
                    "Step A: 恢复后仍在招呼子页面（检测到 accept_button）"
                )
            elif row_rid and row_rid in xml:
                self._logger.info("Step A: 已验证回到主聊天列表")
            else:
                self._logger.warning(
                    "Step A: 无法确认当前页面状态（无 chat_row 无 accept_button）"
                )
        except Exception:
            self._logger.debug("Step A: 页面验证异常", exc_info=True)

        self.last_approved_count = approved_count
        self._logger.info("Step A: 完成，通过 %d 人", approved_count)

    def _step_invite_to_group(self) -> None:
        """本轮刚通过的好友：批量邀请进群后回到消息页。"""
        if not self._approved_this_round:
            self._logger.debug("Step B: 本轮无新通过好友，跳过")
            return

        names = [
            name
            for _uid, name in self._approved_this_round
            if name and name != "unknown"
        ]
        if not names:
            self._logger.warning("Step B: 本轮通过好友无有效昵称，跳过拉群")
            return

        self._logger.info("Step B: 本轮批量拉群 %d 人", len(names))
        picked = 0
        try:
            picked = self._batch_invite_friends(names)
        except DumpRecoveryFailed:
            raise
        except Exception:
            self._logger.exception("Step B: 批量邀请失败")

        if picked <= 0:
            return

        for uid, name in self._approved_this_round:
            try:
                self.storage.mark_status(uid, "done", name=name)
                self.friends_processed_this_round += 1
                self._logger.info("Step B: %s 已邀请进群", name)
            except Exception:
                self._logger.exception("Step B: 更新 %s 状态失败", name)

        if not self._first_greet_batch_done():
            self.storage.set_device_state_flag("first_greet_batch_done", True)
            self._logger.info("Step B: 首批招呼拉群已完成，后续不再校验阈值")
        if self.friends_processed_this_round > 0:
            self.storage.set_device_state_flag("has_ever_invited", True)

    def _batch_invite_friends(self, names: list[str]) -> int:
        """进入群信息 → 邀请面板 → 多选好友 → 完成 → 回到消息列表。返回选中人数。"""
        self.current_phase = Phase.INVITING_TO_GROUP
        group_name = str(self.settings.get("group_name") or "").strip()
        if not group_name:
            self._logger.warning("未配置 group_name，跳过批量邀请")
            return 0

        if not self.inviter.enter_group_info_directly(group_name):
            self._logger.warning("无法进入群信息页「%s」", group_name)
            return 0
        if not self.inviter.open_invite_panel():
            self._logger.warning("无法打开邀请面板")
            self.inviter.go_back_to_chat_list()
            return 0

        picked = self.inviter.select_friends(names)
        if picked <= 0:
            self._logger.warning("邀请面板未选中任何好友")
            self.inviter.go_back_to_chat_list()
            return 0

        self.inviter.confirm_invite()
        self.inviter.go_back_to_chat_list()
        self._logger.info("Step B: 批量邀请完成，选中 %d/%d 人", picked, len(names))
        try:
            ensure_on_chat_list(
                self.driver,
                self.elements,
                logger=self._logger,
                serial=self.serial,
            )
        except DumpRecoveryFailed:
            raise
        except Exception:
            self._logger.exception("Step B: 批量邀请后归位失败")
        return picked

    def _phase4_wait(self) -> None:
        """本轮结束，等待 round_end_wait_s 秒后进入下一轮。"""
        self.current_phase = Phase.IDLE
        self._logger.debug(
            "Phase 4: 等待 %.0f 秒后进入下一轮", self.round_end_wait
        )
        time.sleep(self.round_end_wait)

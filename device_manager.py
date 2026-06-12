"""多设备线程池管理器。

每个设备 = 一个独立线程，持有 DeviceHandler + SessionRound。
对外提供 start/stop/pause/resume + 状态快照。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from actions.ui_hierarchy import DumpRecoveryFailed
from agent_router import NoAgentError, get_router as _get_agent_router
from core.drivers.agent_driver import AgentHandler  # 路线 C — APK Agent（唯一通路）
from core.pipeline import SessionRound
from data.storage import StorageHandler


class DeviceThread:
    """单台设备的自动化线程。"""

    def __init__(
        self,
        serial: str,
        name: str,
        settings: dict,
        elements: dict,
        on_status_change: Optional[Callable] = None,
        slot_index: int = 0,
    ) -> None:
        self.serial = serial
        self.name = name
        self.settings = settings
        self.elements = elements
        self._on_status = on_status_change
        self.slot_index = slot_index

        # 运行时状态
        self._running = False
        self._paused = False
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event()
        self._pause_evt.set()  # 初始不暂停
        self._thread: Optional[threading.Thread] = None

        # 被控组件
        self.driver: Optional[AgentHandler] = None
        self.session_round: Optional[SessionRound] = None
        self.storage: Optional[StorageHandler] = None

        # 状态快照（线程安全，主线程只读）
        self._lock = threading.RLock()
        self._state: str = "stopped"
        self._friend: str = "-"
        self._round: str = "-"
        self._pipeline_state: str = "idle"
        self._error: Optional[str] = None
        self._consecutive_errors: int = 0

        # 新增字段
        self._round_number: str = "0"
        self._friends_total: str = "0"
        self._current_phase: str = "idle"
        self._friends_this_round: str = "0"

        # 账号检测相关字段
        # _check_requested: True 表示主循环跑完当前轮后做一次账号检测
        # _account_status:  "unchecked" | "ok" | "abnormal" | "unknown" | "error"
        # _last_check_at:   最近一次检测完成的时间戳（Unix epoch，秒）
        # _account_message: 异常时的展示文案（可选）
        # _paused_by_account_check: 当前 paused 状态是否由账号检测引起（用于"清除标记后自动恢复"）
        self._check_requested: bool = False
        self._account_status: str = "unchecked"
        self._last_check_at: float = 0.0
        self._account_message: str = ""
        self._paused_by_account_check: bool = False
        # dump 失败等自动暂停时保留，直到 resume 清除
        self._sticky_error: Optional[str] = None

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def thread_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> Dict[str, Any]:
        """线程安全的设备状态快照。"""
        with self._lock:
            return {
                "serial": self.serial,
                "name": self.name,
                "slot_index": self.slot_index,
                "state": self._state,
                "friend": self._friend,
                "round": self._round,
                "pipeline": self._pipeline_state,
                "error": self._error,
                "round_number": self._round_number,
                "friends_total": self._friends_total,
                "current_phase": self._current_phase,
                "friends_this_round": self._friends_this_round,
                # 账号检测字段
                "account_status": self._account_status,
                "last_check_at": self._last_check_at,
                "account_message": self._account_message,
                "check_pending": self._check_requested,
            }

    # ------------------------ 账号检测控制 ------------------------

    def request_account_check(self) -> None:
        """请求在下一轮结束后做一次账号检测。线程安全。"""
        with self._lock:
            self._check_requested = True

    def dismiss_account_status(self) -> bool:
        """清除当前账号异常标记。
        如果设备是因账号检测被暂停的，会自动 resume。
        返回 True 表示有状态被清除。
        """
        changed = False
        should_resume = False
        with self._lock:
            if self._account_status in ("abnormal", "unknown", "error"):
                self._account_status = "unchecked"
                self._account_message = ""
                changed = True
            if self._paused_by_account_check:
                self._paused_by_account_check = False
                should_resume = True
        if should_resume:
            self.resume()
        elif changed and self._on_status:
            try:
                self._on_status(self.snapshot())
            except Exception:
                pass
        return changed

    def start(self) -> bool:
        """启动自动化线程。"""
        if self._thread and self._thread.is_alive():
            return False

        self._stop_evt.clear()
        self._pause_evt.set()
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name=f"device-{self.serial}", daemon=True
        )
        self._thread.start()
        self._set_state("running")
        return True

    def stop(self) -> None:
        """停止自动化线程。"""
        self._running = False
        self._stop_evt.set()
        self._pause_evt.set()  # 取消暂停，让线程退出
        self._set_state("stopped")

    def pause(self, reason: Optional[str] = None) -> None:
        if reason:
            with self._lock:
                self._sticky_error = reason
                self._error = reason
        self._pause_evt.clear()
        self._set_state("paused")

    def resume(self) -> None:
        with self._lock:
            self._sticky_error = None
            self._error = None
        self._pause_evt.set()
        self._set_state("running")

    def reload_config(self, settings: dict, elements: dict) -> None:
        """热更新配置。"""
        self.settings = settings
        self.elements = elements
        if self.session_round:
            self.session_round.apply_config(settings, elements)

    # ------------------------ Agent 连接 ------------------------

    def _agent_is_online(self) -> bool:
        try:
            return _get_agent_router().get(self.serial) is not None
        except Exception:
            return False

    def _wait_for_agent(
        self,
        logger: logging.Logger,
        *,
        initial: bool = False,
    ) -> bool:
        """等待 Agent 上线。返回 False 表示收到停止信号。"""
        backoff = 1.0
        while self._running and not self._stop_evt.is_set():
            if self._agent_is_online():
                with self._lock:
                    if self._error and "Agent" in (self._error or ""):
                        self._error = None
                    self._current_phase = "idle"
                if self._on_status:
                    try:
                        self._on_status(self.snapshot())
                    except Exception:
                        pass
                if not initial:
                    logger.info("设备 %s: Agent 已重连", self.serial)
                return True

            with self._lock:
                self._error = "等待 Agent 连接…"
                self._current_phase = "waiting_agent"
            if self._on_status:
                try:
                    self._on_status(self.snapshot())
                except Exception:
                    pass

            msg = "启动前等待 Agent" if initial else "等待 Agent 重连"
            logger.info("设备 %s: %s (%.0fs 后重试)", self.serial, msg, backoff)
            if self._stop_evt.wait(timeout=backoff):
                return False
            backoff = min(backoff * 1.5, 30.0)
        return False

    # ------------------------ 内部 ------------------------

    def _set_state(self, state: str) -> None:
        with self._lock:
            self._state = state
        if self._on_status:
            try:
                self._on_status(self.snapshot())
            except Exception:
                pass

    def _update_snapshot(self) -> None:
        """从 SessionRound / storage 刷新状态字段并触发回调。"""
        with self._lock:
            if self.session_round:
                self._pipeline_state = self.session_round.current_phase or "idle"
                self._round_number = str(self.session_round.round_number)
                self._current_phase = self.session_round.current_phase or "idle"
                self._friends_this_round = str(self.session_round.friends_processed_this_round)
            if self.storage:
                try:
                    counts = self.storage.count_by_status()
                    self._friends_total = str(counts.get("total", 0))
                except Exception:
                    pass
            if self._sticky_error is None:
                self._error = None
            else:
                self._error = self._sticky_error
        if self._on_status:
            try:
                self._on_status(self.snapshot())
            except Exception:
                pass

    def _run(self) -> None:
        """主循环：while running → execute_one_round() → sleep(round_end_wait_s)。

        驱动选择策略 (路线 C — 仅 Agent)：
          若 ``AgentRouter`` 上有该 serial 的活跃连接 → 用 ``AgentHandler``；
          否则报错。
        """
        logger = logging.getLogger(f"device.{self.serial}")
        logger.info("设备线程启动: %s", self.name)

        # ---------- 驱动选择（仅 Agent，支持启动前 / 运行中等待重连） ----------
        if not self._wait_for_agent(logger, initial=True):
            logger.info("设备 %s: 停止信号，未等到 Agent", self.serial)
            with self._lock:
                self._state = "stopped"
            return

        try:
            agent_conn = _get_agent_router().get(self.serial)
            if agent_conn is None:
                raise RuntimeError(f"设备 {self.serial} Agent 连接不可用")
            logger.info("设备 %s 使用 APK Agent (路线 C)", self.serial)
            self.driver = AgentHandler(
                "config/settings.yaml", serial=agent_conn.serial
            )
            self.driver.ensure_input_ime_ready()
        except Exception:
            logger.exception("连接设备失败: %s", self.serial)
            with self._lock:
                self._error = "连接失败"
                self._state = "error"
            if self._on_status:
                try:
                    self._on_status(self.snapshot())
                except Exception:
                    pass
            return

        # ---------- 业务组件初始化 ----------
        try:
            self.storage = StorageHandler.for_serial(self.serial)
            self.session_round = SessionRound(
                self.driver,
                self.elements,
                self.settings,
                self.storage,
                serial=self.serial,
            )
        except Exception:
            logger.exception("初始化组件失败")
            with self._lock:
                self._error = "初始化失败"
                self._state = "error"
            return

        round_end_wait = float(self.settings.get("round_end_wait_s", 10))
        max_errors = int(self.settings.get("max_consecutive_errors", 5))
        consecutive_errors = 0

        try:
            # 线程启动时执行一次上号（用户已手动回桌面）；账号正常时轮次内不再重复。
            try:
                self._run_initial_account_boot(logger)
            except DumpRecoveryFailed as dump_exc:
                logger.error("设备 %s: 启动上号 dump 失败 — %s", self.serial, dump_exc)
                self.pause(reason=str(dump_exc))
            except Exception as boot_exc:
                from core.account_boot import BootStepFailed

                if isinstance(boot_exc, BootStepFailed):
                    self._pause_boot_failure(logger, boot_exc)
                else:
                    logger.exception("设备 %s: 启动时自动上号异常", self.serial)
            if self._stop_evt.is_set():
                return

            while self._running and not self._stop_evt.is_set():
                # 暂停闸
                while not self._pause_evt.is_set() and not self._stop_evt.is_set():
                    time.sleep(0.2)

                if self._stop_evt.is_set():
                    break

                # 账号检测 hook：在每轮开始前判定。
                # 这样 trigger 的语义是"完成当前轮后再检测" — 符合用户需求。
                # （触发时刻所在的那一轮自然走完 → 回到循环顶部 → 这里命中）
                if self._check_requested:
                    self._check_requested = False
                    try:
                        self._do_account_check(logger)
                    except Exception:
                        logger.exception("设备 %s 账号检测主流程异常", self.serial)
                    # 检测里可能调用了 pause()，下一次循环顶部会重新挡在暂停闸
                    if self._stop_evt.is_set():
                        break

                if not self._agent_is_online():
                    logger.warning("设备 %s: Agent 离线，进入等待", self.serial)
                    if not self._wait_for_agent(logger):
                        break
                    continue

                try:
                    # 执行一整轮（内部已包含 Phase 4 等待）
                    self.session_round.execute_one_round()
                    consecutive_errors = 0
                    self._update_snapshot()
                    try:
                        self._maybe_check_low_greet(logger)
                    except Exception:
                        logger.exception("设备 %s: 低招呼检测异常", self.serial)
                    try:
                        self._maybe_post_dynamic_no_greet_swap(logger)
                    except Exception:
                        logger.exception("设备 %s: 发动态后无招呼换号等待异常", self.serial)

                except DumpRecoveryFailed as dump_exc:
                    reason = str(dump_exc)
                    logger.error("设备 %s: %s", self.serial, reason)
                    self.pause(reason=reason)
                    consecutive_errors = 0
                    continue

                except NoAgentError:
                    logger.warning("设备 %s: Agent RPC 断开，等待重连", self.serial)
                    if not self._wait_for_agent(logger):
                        break
                    continue

                except Exception:
                    logger.exception("设备 %s 轮次异常", self.serial)
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.error("连续异常 %d 次，设备 %s 停止", consecutive_errors, self.serial)
                        with self._lock:
                            self._error = f"连续异常{consecutive_errors}次"
                            self._state = "error"
                        break

                # 轮次间短暂让渡（主要等待已在 _phase4_wait 内完成）
                time.sleep(0.5)

        finally:
            logger.info("设备线程退出: %s", self.name)
            self._running = False
            with self._lock:
                self._state = "stopped"

    def _run_initial_account_boot(self, logger: logging.Logger) -> None:
        """设备线程启动时执行一次完整上号（假定用户已在桌面）。"""
        boot_cfg = (self.settings or {}).get("account_boot") or {}
        if not boot_cfg.get("enabled", True):
            return
        self._do_account_boot(logger)

    def _pause_boot_failure(self, logger: logging.Logger, exc: Exception) -> None:
        from core.account_boot import BootStepFailed

        if isinstance(exc, BootStepFailed):
            msg = f"上号失败 [{exc.step}]: {exc.reason}"
        else:
            msg = f"上号失败: {exc}"
        logger.error("设备 %s: %s", self.serial, msg)
        self.pause(reason=msg)

    def _do_account_boot(self, logger: logging.Logger) -> None:
        """执行微霸上号 + 发动态（含回到消息 Tab）。任一步失败则暂停，不进入招呼。"""
        from core.account_boot import BootResult, BootStepFailed, run_account_boot
        from core.post_dynamic import run_post_dynamic

        if self.driver is None:
            return
        logger.info("设备 %s: 开始自动上号", self.serial)
        try:
            result = run_account_boot(
                self.driver,
                self.elements,
                self.settings,
                logger=logger,
                slot_index=self.slot_index,
            )
        except BootStepFailed as exc:
            self._pause_boot_failure(logger, exc)
            raise
        except DumpRecoveryFailed:
            raise
        except Exception:
            logger.exception("设备 %s: run_account_boot 抛异常", self.serial)
            self._pause_boot_failure(logger, BootStepFailed("account_boot", "上号流程异常"))
            raise

        if result is BootResult.FAILED:
            self._pause_boot_failure(logger, BootStepFailed("account_boot", "上号返回失败"))
            raise BootStepFailed("account_boot", "上号返回失败")

        if result is not BootResult.SUCCESS:
            return

        try:
            run_post_dynamic(
                self.driver, self.elements, self.settings, logger=logger,
                slot_index=self.slot_index,
            )
        except BootStepFailed as exc:
            self._pause_boot_failure(logger, exc)
            raise
        except Exception:
            logger.exception("设备 %s: post_dynamic 异常", self.serial)
            self._pause_boot_failure(logger, BootStepFailed("post_dynamic", "发动态异常"))
            raise
        self._on_post_dynamic_done(logger)

    def _resolve_current_account_filename(self, explicit: str = "") -> str:
        name = (explicit or "").strip()
        if name:
            return name
        try:
            from data.file_pool import get_pool_status

            assignments = get_pool_status().get("assignments") or {}
            return str(assignments.get(self.serial) or "").strip()
        except Exception:
            return ""

    def _begin_new_account_session(self, filename: str, logger: logging.Logger) -> None:
        """换号或新号：重置招呼状态并记录当前号文件名。"""
        if self.storage is None:
            return
        fn = (filename or "").strip() or self._resolve_current_account_filename()
        try:
            if fn:
                self.storage.set_device_state_field("current_account_filename", fn)
            self.storage.set_device_state_flag("has_ever_invited", False)
            self.storage.set_device_state_flag("first_greet_batch_done", False)
            self.storage.set_device_state_flag("low_greet_reported", False)
            self.storage.set_device_state_field("post_dynamic_at", 0)
            logger.info("设备 %s: 新号会话 filename=%s", self.serial, fn or "-")
        except Exception:
            logger.exception("设备 %s: 重置新号会话状态失败", self.serial)

    def _on_post_dynamic_done(self, logger: logging.Logger) -> None:
        if self.storage is None:
            return
        try:
            fn = self._resolve_current_account_filename()
            if fn:
                self.storage.set_device_state_field("current_account_filename", fn)
            self.storage.set_device_state_field("post_dynamic_at", time.time())
            self.storage.set_device_state_flag("low_greet_reported", False)
        except Exception:
            logger.exception("设备 %s: 记录发动态时间失败", self.serial)

    def _on_abnormal_mode(self) -> str:
        ac_cfg = (self.settings or {}).get("account_check") or {}
        return str(ac_cfg.get("on_abnormal") or "continue").lower()

    def _maybe_pause_after_swap_success(
        self, logger: logging.Logger, *, reason: str
    ) -> None:
        """换号全流程成功后：仅 on_abnormal=pause 时暂停。"""
        if self._on_abnormal_mode() == "pause":
            with self._lock:
                self._paused_by_account_check = True
            self.pause(reason=reason)

    def _continue_account_after_swap(self, filename: str, logger: logging.Logger) -> bool:
        """换号推送并刷新后：第一个文件号 → 一键切换 → 打开陌陌 → 发动态。"""
        from core.account_boot import BootResult, BootStepFailed, run_account_boot_from_phone
        from core.post_dynamic import run_post_dynamic
        from core.weiba_refresh import ensure_weiba_phone_and_refresh

        if self.driver is None:
            return False
        try:
            refreshed = ensure_weiba_phone_and_refresh(
                self.driver,
                self.elements,
                self.settings,
                logger=logger,
            )
            if not refreshed:
                logger.warning("设备 %s: 换号后刷新微霸失败", self.serial)
                self.pause(reason="换号失败: 未能回到微霸并刷新")
                return False
        except Exception:
            logger.exception("设备 %s: 换号后刷新微霸异常", self.serial)
            self.pause(reason="换号失败: 回微霸异常")
            return False

        try:
            boot_result = run_account_boot_from_phone(
                self.driver,
                self.elements,
                self.settings,
                logger=logger,
                slot_index=self.slot_index,
            )
        except BootStepFailed as exc:
            self._pause_boot_failure(logger, exc)
            return False
        except DumpRecoveryFailed:
            raise
        except Exception:
            logger.exception("设备 %s: 换号后续上号异常", self.serial)
            self._pause_boot_failure(
                logger, BootStepFailed("account_boot_from_phone", "换号后续上号异常")
            )
            return False
        if boot_result is BootResult.FAILED:
            self._pause_boot_failure(
                logger, BootStepFailed("account_boot_from_phone", "换号后续上号失败")
            )
            return False

        self._begin_new_account_session(filename, logger)
        try:
            run_post_dynamic(
                self.driver, self.elements, self.settings, logger=logger,
                slot_index=self.slot_index,
            )
        except BootStepFailed as exc:
            self._pause_boot_failure(logger, exc)
            return False
        except Exception:
            logger.exception("设备 %s: 换号后 post_dynamic 异常", self.serial)
            self._pause_boot_failure(logger, BootStepFailed("post_dynamic", "换号后发动态异常"))
            return False
        self._on_post_dynamic_done(logger)
        return True

    def _swap_and_continue_account(
        self, logger: logging.Logger, *, reason: str = ""
    ) -> bool:
        """推送新号文件并完成微霸上号 + 发动态；失败暂停，成功按 on_abnormal 决定是否暂停。"""
        from ops.account_swap import swap_account_file_for_device
        from ops.agent_init import agent_serial_to_adb_serial

        ac_cfg = (self.settings or {}).get("account_check") or {}
        local_dir = str(ac_cfg.get("local_dir") or "").strip()
        remote_dir = str(ac_cfg.get("remote_dir") or "/sdcard/Download").strip()
        tag = reason or "换号"

        if not local_dir:
            msg = "换号失败: 未配置 account_check.local_dir"
            logger.warning("设备 %s: %s", self.serial, msg)
            with self._lock:
                self._account_message = msg
            self.pause(reason=msg)
            return False

        adb_serial = agent_serial_to_adb_serial(self.serial)
        result = swap_account_file_for_device(
            adb_serial,
            local_dir,
            remote_dir,
            agent_serial=self.serial,
        )
        if not result.get("ok"):
            err = str(result.get("error") or "换号失败")
            logger.error("设备 %s: %s — %s", self.serial, tag, err)
            with self._lock:
                self._account_message = err
            self.pause(reason=f"换号失败: {err}")
            return False

        filename = str(result.get("file") or "")
        logger.info(
            "设备 %s: %s 换号成功 %s → %s",
            self.serial,
            tag,
            filename,
            result.get("remote"),
        )

        continued = False
        if self.driver is not None:
            try:
                continued = self._continue_account_after_swap(filename, logger)
            except DumpRecoveryFailed:
                raise
            except Exception:
                logger.exception("设备 %s: 换号后衔接新号流程异常", self.serial)
                self.pause(reason="换号失败: 衔接新号异常")
                return False

        if not continued:
            return False

        with self._lock:
            self._account_message = f"已换号: {filename}，已衔接新号上号"
            self._account_status = "ok"
        self._maybe_pause_after_swap_success(
            logger, reason=f"{tag}，已换号，请处理后恢复"
        )
        if self._on_status:
            try:
                self._on_status(self.snapshot())
            except Exception:
                pass
        return True

    def _maybe_check_low_greet(self, logger: logging.Logger) -> None:
        if self.session_round is None or self.storage is None or self.driver is None:
            return
        from core.low_greet_watch import maybe_report_low_greet

        maybe_report_low_greet(
            greeter=self.session_round.greeter,
            storage=self.storage,
            settings=self.settings,
            serial=self.serial,
            device_name=self.name,
            logger=logger,
        )

    def _maybe_post_dynamic_no_greet_swap(self, logger: logging.Logger) -> None:
        """发动态后连续 N 分钟无招呼：直接换号（不检测）。"""
        if self.session_round is None or self.storage is None or self.driver is None:
            return
        if self.session_round.last_approved_count > 0:
            return

        from core.post_dynamic_idle import wait_after_post_dynamic_no_greet

        def _should_stop() -> bool:
            return self._stop_evt.is_set()

        def _should_pause() -> bool:
            with self._lock:
                return not self._pause_evt.is_set()

        def _on_swap(reason: str) -> bool:
            return self._swap_and_continue_account(logger, reason=reason)

        wait_after_post_dynamic_no_greet(
            greeter=self.session_round.greeter,
            storage=self.storage,
            settings=self.settings,
            should_stop=_should_stop,
            should_pause=_should_pause,
            on_swap_account=_on_swap,
            logger=logger,
        )

    def _do_account_check(self, logger: logging.Logger) -> None:
        """跑一次账号检测，处理结果。

        on_abnormal 策略 (来自 settings.account_check.on_abnormal):
          - "continue"  → 异常时换号并继续（成功不暂停）
          - "pause"     → 异常换号成功后仍暂停
          - "mark_only" → 仅打标，不触发换号
        """
        from core.account_check import run_account_check, AccountCheckResult

        if self.driver is None:
            return

        ac_cfg = (self.settings or {}).get("account_check") or {}
        timeout = float(ac_cfg.get("detect_timeout_sec") or 8.0)
        on_abnormal = self._on_abnormal_mode()

        logger.info("设备 %s: 开始账号检测", self.serial)
        try:
            result = run_account_check(
                self.driver,
                self.elements,
                detect_timeout_sec=timeout,
                logger=logger,
            )
        except Exception:
            logger.exception("设备 %s: run_account_check 抛异常", self.serial)
            result = AccountCheckResult.ERROR

        with self._lock:
            self._account_status = result.value
            self._last_check_at = time.time()
            if result is AccountCheckResult.ABNORMAL:
                self._account_message = "账号异常"
            elif result is AccountCheckResult.UNKNOWN:
                self._account_message = "状态未知"
            elif result is AccountCheckResult.ERROR:
                self._account_message = "检测失败"
            else:
                self._account_message = ""

        if result is AccountCheckResult.ABNORMAL and on_abnormal != "mark_only":
            self._swap_and_continue_account(logger, reason="账号异常")
        elif self._on_status:
            try:
                self._on_status(self.snapshot())
            except Exception:
                pass


class DeviceManager:
    """管理多台设备的启停与状态聚合。"""

    def __init__(
        self,
        device_list: List[Dict[str, str]],
        settings: dict,
        elements: dict,
        on_status_change: Optional[Callable] = None,
    ) -> None:
        self.settings = settings
        self.elements = elements
        self._on_status = on_status_change
        self._lock = threading.RLock()
        self._threads: Dict[str, DeviceThread] = {}

        for idx, dev in enumerate(device_list):
            serial = dev["serial"]
            name = dev.get("name", serial)
            self._threads[serial] = DeviceThread(
                serial, name, settings, elements,
                on_status_change=on_status_change,
                slot_index=idx,
            )

        # ---------- 账号检测调度 ----------
        ac_cfg = (settings or {}).get("account_check") or {}
        # 配置缓存（前端可以通过 set_account_check_config 修改并即时生效）
        self._ac_enabled: bool = bool(ac_cfg.get("enabled", False))
        try:
            self._ac_interval_min: int = max(1, int(ac_cfg.get("interval_minutes", 30)))
        except Exception:
            self._ac_interval_min = 30
        self._ac_on_abnormal: str = str(ac_cfg.get("on_abnormal") or "continue").lower()
        # 调度器：daemon 线程，每分钟检查一次是否到点
        self._ac_scheduler_evt = threading.Event()
        self._ac_scheduler_thread: Optional[threading.Thread] = None
        self._ac_last_trigger_at: float = 0.0  # 最近一次（自动 or 手动）触发的时间
        self._start_ac_scheduler()

    # ------------------------ 控制接口 ------------------------

    def start_all(self) -> None:
        """启动所有已注册设备（不自动添加在线 Agent）。"""
        for dt in self._threads.values():
            dt.start()

    def start_all_online(self) -> int:
        """为每个 WebSocket 在线 Agent 自动 add_device 并 start。返回本次新启动数量。"""
        log = logging.getLogger("device_manager")
        try:
            serials = _get_agent_router().list_serials()
        except Exception:
            log.exception("列举在线 Agent 失败")
            return 0

        started = 0
        for serial in serials:
            try:
                self.add_device(serial, serial)
                dt = self._threads.get(serial)
                if dt is None:
                    continue
                if dt.state == "running":
                    continue
                if dt.state == "paused" and dt.thread_alive:
                    dt.resume()
                    started += 1
                elif self.start_device(serial):
                    started += 1
            except Exception:
                log.exception("启动在线 Agent 失败: %s", serial)
        log.info("全部启动（在线 Agent）: %d 台在线, %d 台新启动", len(serials), started)
        return started

    def stop_all(self) -> None:
        """停止所有设备。"""
        for dt in self._threads.values():
            dt.stop()

    def pause_all(self) -> None:
        for dt in self._threads.values():
            if dt.state == "running":
                dt.pause()

    def resume_all(self) -> None:
        for dt in self._threads.values():
            if dt.state != "paused":
                continue
            if dt.thread_alive:
                dt.resume()
            else:
                dt.start()

    def add_device(self, serial: str, name: Optional[str] = None) -> Optional["DeviceThread"]:
        """新增一台设备（线程安全）。已存在返回 None。"""
        name = (name or "").strip() or serial
        with self._lock:
            if serial in self._threads:
                return None
            slot_index = len(self._threads)
            dt = DeviceThread(
                serial, name, self.settings, self.elements,
                on_status_change=self._on_status,
                slot_index=slot_index,
            )
            self._threads[serial] = dt
            return dt

    def remove_device(self, serial: str) -> bool:
        """移除一台设备（线程安全），返回是否实际移除。"""
        with self._lock:
            dt = self._threads.pop(serial, None)
        if dt:
            try:
                dt.stop()
            except Exception:
                logging.getLogger("device_manager").exception("停止设备线程失败: %s", serial)
            return True
        return False

    def start_device(self, serial: str) -> bool:
        dt = self._threads.get(serial)
        if dt:
            return dt.start()
        return False

    def stop_device(self, serial: str) -> None:
        dt = self._threads.get(serial)
        if dt:
            dt.stop()

    def pause_device(self, serial: str) -> None:
        dt = self._threads.get(serial)
        if dt:
            dt.pause()

    def resume_device(self, serial: str) -> None:
        dt = self._threads.get(serial)
        if not dt:
            return
        if dt.thread_alive:
            dt.resume()
        else:
            dt.start()

    def reload_config(self, settings: dict, elements: dict) -> None:
        """热更新所有设备配置。"""
        self.settings = settings
        self.elements = elements
        for dt in self._threads.values():
            dt.reload_config(settings, elements)

    # ------------------------ 状态 ------------------------

    def get_all_status(self) -> List[Dict[str, Any]]:
        """返回所有设备的状态快照。"""
        with self._lock:
            threads = list(self._threads.values())
        return [dt.snapshot() for dt in threads]

    def get_device_status(self, serial: str) -> Optional[Dict[str, Any]]:
        dt = self._threads.get(serial)
        return dt.snapshot() if dt else None

    # ------------------------ 账号检测 ------------------------

    def set_account_check_config(
        self,
        *,
        enabled: Optional[bool] = None,
        interval_minutes: Optional[int] = None,
        on_abnormal: Optional[str] = None,
        idle_after_invite_minutes: Optional[float] = None,
        post_dynamic_no_greet_swap_minutes: Optional[float] = None,
        local_dir: Optional[str] = None,
        remote_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新账号检测配置。任一字段传 None 表示不修改。
        返回当前生效的配置。"""
        with self._lock:
            if enabled is not None:
                self._ac_enabled = bool(enabled)
            if interval_minutes is not None:
                try:
                    self._ac_interval_min = max(1, int(interval_minutes))
                except Exception:
                    pass
            if on_abnormal is not None:
                v = str(on_abnormal).lower()
                if v in ("pause", "mark_only", "continue"):
                    self._ac_on_abnormal = v
            # 同步到 settings dict（让每个 DeviceThread 都能拿到 detect_timeout / on_abnormal）
            cfg = self.settings.setdefault("account_check", {}) if isinstance(self.settings, dict) else None
            if isinstance(cfg, dict):
                cfg["enabled"] = self._ac_enabled
                cfg["interval_minutes"] = self._ac_interval_min
                cfg["on_abnormal"] = self._ac_on_abnormal
                if idle_after_invite_minutes is not None:
                    try:
                        cfg["idle_after_invite_minutes"] = max(
                            1.0, float(idle_after_invite_minutes)
                        )
                    except (TypeError, ValueError):
                        pass
                if post_dynamic_no_greet_swap_minutes is not None:
                    try:
                        cfg["post_dynamic_no_greet_swap_minutes"] = max(
                            0.0, float(post_dynamic_no_greet_swap_minutes)
                        )
                    except (TypeError, ValueError):
                        pass
                if local_dir is not None:
                    cfg["local_dir"] = str(local_dir).strip()
                if remote_dir is not None:
                    cfg["remote_dir"] = str(remote_dir).strip() or "/sdcard/Download"
            # 任一更改都重置"上次触发时间"，让 enable 后立刻按周期开始计时
            # （但不会立即触发，立刻触发请用 trigger_account_check_all）
            self._ac_last_trigger_at = time.time()
        # 唤醒调度器线程立刻醒来重新计算（调度器醒来后会自行 clear）
        self._ac_scheduler_evt.set()
        return self.get_account_check_config()

    def get_account_check_config(self) -> Dict[str, Any]:
        with self._lock:
            ac = (self.settings or {}).get("account_check") or {}
            return {
                "enabled": self._ac_enabled,
                "interval_minutes": self._ac_interval_min,
                "on_abnormal": self._ac_on_abnormal,
                "idle_after_invite_minutes": float(
                    ac.get("idle_after_invite_minutes", 5)
                ),
                "post_dynamic_no_greet_swap_minutes": float(
                    ac.get("post_dynamic_no_greet_swap_minutes", 5)
                ),
                "local_dir": str(ac.get("local_dir") or ""),
                "remote_dir": str(ac.get("remote_dir") or "/sdcard/Download"),
            }

    def trigger_account_check_all(self) -> int:
        """立即对所有 running 设备置 check_requested。
        返回被触发的设备数。"""
        n = 0
        with self._lock:
            threads = list(self._threads.values())
        for dt in threads:
            # 只对 running 的设备触发（stopped/error/paused 设备无意义）
            if dt.state == "running":
                dt.request_account_check()
                n += 1
        with self._lock:
            self._ac_last_trigger_at = time.time()
        return n

    def trigger_account_check_one(self, serial: str) -> bool:
        dt = self._threads.get(serial)
        if not dt:
            return False
        if dt.state != "running":
            return False
        dt.request_account_check()
        return True

    def dismiss_account_status(self, serial: str) -> bool:
        dt = self._threads.get(serial)
        if not dt:
            return False
        return dt.dismiss_account_status()

    def get_account_check_status(self) -> Dict[str, Any]:
        """聚合所有设备的检测状态，供前端轮询。"""
        with self._lock:
            cfg = dict(self.get_account_check_config())
            cfg["last_trigger_at"] = self._ac_last_trigger_at
            threads = list(self._threads.values())
        devices = []
        for dt in threads:
            snap = dt.snapshot()
            devices.append({
                "serial": snap["serial"],
                "name": snap.get("name") or snap["serial"],
                "state": snap["state"],
                "account_status": snap.get("account_status", "unchecked"),
                "last_check_at": snap.get("last_check_at", 0.0),
                "account_message": snap.get("account_message", ""),
                "check_pending": snap.get("check_pending", False),
            })
        return {"config": cfg, "devices": devices}

    # ---------- 调度器 ----------

    def _start_ac_scheduler(self) -> None:
        if self._ac_scheduler_thread and self._ac_scheduler_thread.is_alive():
            return
        self._ac_scheduler_thread = threading.Thread(
            target=self._ac_scheduler_loop,
            name="account-check-scheduler",
            daemon=True,
        )
        self._ac_scheduler_thread.start()

    def _ac_scheduler_loop(self) -> None:
        """周期触发器。每 ~10s 醒来一次，看是否到点。"""
        log = logging.getLogger("account_check.scheduler")
        log.info("账号检测调度器启动")
        while True:
            # 等下一次唤醒 — set_account_check_config 也会立刻唤醒（通过 .set()）
            # 这里 clear() 是为了让下一次 wait 能重新阻塞；超时唤醒不需要 clear
            self._ac_scheduler_evt.wait(timeout=10.0)
            self._ac_scheduler_evt.clear()
            try:
                with self._lock:
                    enabled = self._ac_enabled
                    interval_sec = self._ac_interval_min * 60
                    last = self._ac_last_trigger_at
                if not enabled:
                    continue
                now = time.time()
                # 首次启用时 last_trigger_at 在 set_account_check_config 里被设为 now，
                # 即从启用时刻开始计时，避免一启用就立刻触发。
                if last <= 0:
                    with self._lock:
                        self._ac_last_trigger_at = now
                    continue
                if now - last >= interval_sec:
                    n = self.trigger_account_check_all()
                    log.info("定时触发账号检测，命中 %d 台设备", n)
            except Exception:
                log.exception("调度器循环异常")

"""多设备线程池管理器。

每个设备 = 一个独立线程，持有 DeviceHandler + SessionRound。
对外提供 start/stop/pause/resume + 状态快照。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import uiautomator2 as u2

from core.driver import DeviceHandler
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
    ) -> None:
        self.serial = serial
        self.name = name
        self.settings = settings
        self.elements = elements
        self._on_status = on_status_change

        # 运行时状态
        self._running = False
        self._paused = False
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event()
        self._pause_evt.set()  # 初始不暂停
        self._thread: Optional[threading.Thread] = None

        # 被控组件
        self.driver: Optional[DeviceHandler] = None
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

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def snapshot(self) -> Dict[str, Any]:
        """线程安全的设备状态快照。"""
        with self._lock:
            return {
                "serial": self.serial,
                "name": self.name,
                "state": self._state,
                "friend": self._friend,
                "round": self._round,
                "pipeline": self._pipeline_state,
                "error": self._error,
                "round_number": self._round_number,
                "friends_total": self._friends_total,
                "current_phase": self._current_phase,
                "friends_this_round": self._friends_this_round,
            }

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

    def pause(self) -> None:
        self._pause_evt.clear()
        self._set_state("paused")

    def resume(self) -> None:
        self._pause_evt.set()
        self._set_state("running")

    def reload_config(self, settings: dict, elements: dict) -> None:
        """热更新配置。"""
        self.settings = settings
        self.elements = elements
        if self.session_round:
            self.session_round.settings = settings
            self.session_round.elements = elements
            self.session_round.N = max(1, int(settings.get("chat_rounds_before_follow", 3)))
            self.session_round.S = max(1, int(settings.get("max_chat_rounds", 10)))
            self.session_round.round_end_wait = float(settings.get("round_end_wait_s", 10))

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
            self._error = None
        if self._on_status:
            try:
                self._on_status(self.snapshot())
            except Exception:
                pass

    def _run(self) -> None:
        """主循环：while running → execute_one_round() → sleep(round_end_wait_s)。"""
        logger = logging.getLogger(f"device.{self.serial}")
        logger.info("设备线程启动: %s", self.name)

        # 连接设备
        try:
            d = u2.connect(self.serial)
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

        # 初始化组件
        try:
            self.driver = DeviceHandler("config/settings.yaml")
            self.driver.d = d
            self.driver.ensure_input_ime_ready()
            self.storage = StorageHandler("data/friends.json")
            self.session_round = SessionRound(
                self.driver, self.elements, self.settings, self.storage
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
            while self._running and not self._stop_evt.is_set():
                # 暂停闸
                while not self._pause_evt.is_set() and not self._stop_evt.is_set():
                    time.sleep(0.2)

                if self._stop_evt.is_set():
                    break

                try:
                    # 执行一整轮（内部已包含 Phase 4 等待）
                    self.session_round.execute_one_round()
                    consecutive_errors = 0
                    self._update_snapshot()

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

        for dev in device_list:
            serial = dev["serial"]
            name = dev.get("name", serial)
            self._threads[serial] = DeviceThread(
                serial, name, settings, elements,
                on_status_change=on_status_change,
            )

    # ------------------------ 控制接口 ------------------------

    def start_all(self) -> None:
        """启动所有设备。"""
        for dt in self._threads.values():
            dt.start()

    def stop_all(self) -> None:
        """停止所有设备。"""
        for dt in self._threads.values():
            dt.stop()

    def pause_all(self) -> None:
        for dt in self._threads.values():
            dt.pause()

    def resume_all(self) -> None:
        for dt in self._threads.values():
            dt.resume()

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
        if dt:
            dt.resume()

    def reload_config(self, settings: dict, elements: dict) -> None:
        """热更新所有设备配置。"""
        self.settings = settings
        self.elements = elements
        for dt in self._threads.values():
            dt.reload_config(settings, elements)

    # ------------------------ 状态 ------------------------

    def get_all_status(self) -> List[Dict[str, Any]]:
        """返回所有设备的状态快照。"""
        return [dt.snapshot() for dt in self._threads.values()]

    def get_device_status(self, serial: str) -> Optional[Dict[str, Any]]:
        dt = self._threads.get(serial)
        return dt.snapshot() if dt else None

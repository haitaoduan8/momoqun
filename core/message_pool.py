"""消息池：按"轮次"顺序选择消息池，并在池内随机选择一句话术。

per-device 模式：每台设备一个 ``data/state/<serial>.json``，互不污染轮次。
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import shutil
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional


_DATA_ROOT = "data"
_STATE_DIR = os.path.join(_DATA_ROOT, "state")
_ARCHIVE_ROOT = os.path.join(_DATA_ROOT, "archive", "state")
_LEGACY_PATH = os.path.join(_DATA_ROOT, "state.json")
_DEFAULT_SERIAL = "default"
_MAX_ARCHIVES_PER_SERIAL = 10


def _sanitize_serial(serial: Optional[str]) -> str:
    if not serial:
        return _DEFAULT_SERIAL
    cleaned = re.sub(r"[^\w\.\-]+", "_", serial.strip())
    return cleaned or _DEFAULT_SERIAL


def state_path_for(serial: Optional[str]) -> str:
    return os.path.join(_STATE_DIR, f"{_sanitize_serial(serial)}.json")


def archive_dir_for(serial: Optional[str]) -> str:
    return os.path.join(_ARCHIVE_ROOT, _sanitize_serial(serial))


def list_existing_serials() -> List[str]:
    if not os.path.isdir(_STATE_DIR):
        return []
    return [name[:-5] for name in os.listdir(_STATE_DIR) if name.endswith(".json")]


class MessagePoolManager:
    """
    - 第 1 轮 -> 池 1
    - 第 2 轮 -> 池 2
    - ... 用完循环
    """

    def __init__(
        self,
        settings_config,
        state_path: Optional[str] = None,
        serial: Optional[str] = None,
    ):
        # 路径解析优先级：
        #   1. 显式 serial → data/state/<serial>.json
        #   2. 显式 state_path（兼容旧调用）
        #   3. 默认 → data/state/default.json
        if serial is not None:
            self.serial: str = _sanitize_serial(serial)
            self.state_path: str = state_path_for(serial)
        elif state_path is not None:
            self.state_path = state_path
            if os.path.abspath(state_path) == os.path.abspath(_LEGACY_PATH):
                self.serial = _DEFAULT_SERIAL
            else:
                base = os.path.basename(state_path)
                self.serial = base[:-5] if base.endswith(".json") else _DEFAULT_SERIAL
        else:
            self.serial = _DEFAULT_SERIAL
            self.state_path = state_path_for(None)

        self._lock = threading.RLock()
        self.cfg: dict = {}
        self.pools: list = []
        self.strategy = "sequential"
        self.reload_from_config(settings_config)
        self._ensure_state_file()

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def reload_from_config(self, settings_config):
        """刷新运行中的消息池配置，供参数面板保存后复用。"""
        cfg = settings_config or {}
        pools = cfg.get("message_pools") or []
        if not isinstance(pools, list) or len(pools) == 0:
            raise ValueError("settings.yaml 中 config.message_pools 不能为空")

        rot = cfg.get("message_pool_rotation") or {}
        strategy = (rot.get("strategy") or "sequential").strip().lower()
        if strategy not in {"sequential"}:
            raise ValueError(f"不支持的 message_pool_rotation.strategy: {strategy}")

        self.cfg = cfg
        self.pools = pools
        self.strategy = strategy

    # ------------------------------------------------------------------
    # 文件读写
    # ------------------------------------------------------------------
    def _ensure_state_file(self):
        parent = os.path.dirname(self.state_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(self.state_path):
            self._write_state({"reply_round": 0})

    def _read_state(self):
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if not isinstance(data, dict):
                return {"reply_round": 0}
            rr = data.get("reply_round")
            if not isinstance(rr, int) or rr < 0:
                rr = 0
            return {"reply_round": rr}
        except Exception:
            # 文件损坏/空文件等情况：重置
            return {"reply_round": 0}

    def _write_state(self, state):
        tmp = f"{self.state_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.state_path)

    # ------------------------------------------------------------------
    # 安全退出归档
    # ------------------------------------------------------------------
    def archive_and_clear(self, *, keep_last: int = _MAX_ARCHIVES_PER_SERIAL) -> Optional[str]:
        with self._lock:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            archived: Optional[str] = None
            try:
                if os.path.exists(self.state_path) and os.path.getsize(self.state_path) > 2:
                    arc_dir = archive_dir_for(self.serial)
                    os.makedirs(arc_dir, exist_ok=True)
                    archived = os.path.join(arc_dir, f"state.{ts}.json")
                    shutil.copy2(self.state_path, archived)
                self._write_state({"reply_round": 0})
                # 滚动清理
                try:
                    arc_dir = archive_dir_for(self.serial)
                    if os.path.isdir(arc_dir):
                        files = sorted(
                            (
                                os.path.join(arc_dir, n)
                                for n in os.listdir(arc_dir)
                                if n.startswith("state.") and n.endswith(".json")
                            ),
                            reverse=True,
                        )
                        for old in files[keep_last:]:
                            try:
                                os.remove(old)
                            except OSError:
                                pass
                except Exception:
                    logging.exception("清理旧 state 归档失败")
            except Exception:
                logging.exception("state archive_and_clear 失败: %s", self.state_path)
            return archived

    # ------------------------------------------------------------------
    # 业务接口
    # ------------------------------------------------------------------
    def _pool_for_round(self, reply_round_1_based):
        idx = (reply_round_1_based - 1) % len(self.pools)
        return self.pools[idx]

    def next_message(self):
        """进入下一轮：轮次 +1，并返回本轮随机选中的回复内容。"""
        with self._lock:
            state = self._read_state()
            state["reply_round"] += 1
            rr = state["reply_round"]

            pool = self._pool_for_round(rr)
            messages = pool.get("messages") if isinstance(pool, dict) else None
            if not isinstance(messages, list) or len(messages) == 0:
                raise ValueError(
                    f"消息池为空或格式错误（第 {((rr - 1) % len(self.pools)) + 1} 个池）"
                )

            msg = random.choice([m for m in messages if isinstance(m, str) and m.strip()])
            if not msg:
                raise ValueError("消息池 messages 中没有有效字符串")

            self._write_state(state)
            return msg

    def peek_round(self):
        """返回当前已使用到的轮次（0 表示还未开始）。"""
        return self._read_state().get("reply_round", 0)

    def get_message_for_round(self, round_n: int) -> str:
        """获取第 N 个池（1-based）中的一条随机消息，不改变内部轮次状态。

        用于按好友 chat_round 选择对应消息池的场景。
        """
        if round_n < 1:
            round_n = 1
        pool = self._pool_for_round(round_n)
        messages = pool.get("messages") if isinstance(pool, dict) else None
        if not isinstance(messages, list) or len(messages) == 0:
            raise ValueError(
                f"消息池为空或格式错误（第 {((round_n - 1) % len(self.pools)) + 1} 个池）"
            )
        msg = random.choice([m for m in messages if isinstance(m, str) and m.strip()])
        if not msg:
            raise ValueError("消息池 messages 中没有有效字符串")
        return msg

    def reset(self):
        """重置轮次为 0。"""
        with self._lock:
            self._write_state(
                {"reply_round": 0, "reset_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            )


# ---------------------------------------------------------------------------
# 进程级归档（供 server 退出钩子调用）
# ---------------------------------------------------------------------------
def archive_and_clear_all_state(*, settings_for_init: Optional[dict] = None) -> Dict[str, Optional[str]]:
    """扫描 ``data/state/`` 下所有 serial 文件并归档清零。

    退出钩子不需要保留消息池配置（直接擦掉 reply_round），所以可以不传 settings；
    但 ``MessagePoolManager`` 构造时会校验 message_pools，故这里走轻量直写而非构造实例。
    """
    results: Dict[str, Optional[str]] = {}
    if not os.path.isdir(_STATE_DIR):
        return results
    for name in os.listdir(_STATE_DIR):
        if not name.endswith(".json"):
            continue
        serial = name[:-5]
        path = os.path.join(_STATE_DIR, name)
        try:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            archived: Optional[str] = None
            if os.path.exists(path) and os.path.getsize(path) > 2:
                arc_dir = archive_dir_for(serial)
                os.makedirs(arc_dir, exist_ok=True)
                archived = os.path.join(arc_dir, f"state.{ts}.json")
                shutil.copy2(path, archived)
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"reply_round": 0}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            results[serial] = archived
        except Exception:
            logging.exception("归档 state 失败: %s", path)
            results[serial] = None
    return results

"""好友库存储。

per-device 模式（多模拟器场景）：每台设备各自一个 ``data/friends/<serial>.json``，
退出时归档到 ``data/archive/friends/<serial>/<timestamp>.json`` 并清零。

兼容旧调用：``StorageHandler("data/friends.json")`` 仍可用（视为 default 设备）。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


ALLOWED_STATUS = {
    "pending",
    "accepted",
    "replied",
    "mutual",
    "pending_followback",
    "followed",
    "done",
    "failed",
}


# ---------------------------------------------------------------------------
# 路径布局
# ---------------------------------------------------------------------------
_DATA_ROOT = "data"
_FRIENDS_DIR = os.path.join(_DATA_ROOT, "friends")
_ARCHIVE_ROOT = os.path.join(_DATA_ROOT, "archive", "friends")
_LEGACY_PATH = os.path.join(_DATA_ROOT, "friends.json")
_DEFAULT_SERIAL = "default"
_MAX_ARCHIVES_PER_SERIAL = 10


def _sanitize_serial(serial: Optional[str]) -> str:
    """`127.0.0.1:5555` → `127.0.0.1_5555`；非法字符全部替换为下划线。"""
    if not serial:
        return _DEFAULT_SERIAL
    cleaned = re.sub(r"[^\w\.\-]+", "_", serial.strip())
    return cleaned or _DEFAULT_SERIAL


def friends_path_for(serial: Optional[str]) -> str:
    """返回某 serial 的 friends json 全路径。"""
    return os.path.join(_FRIENDS_DIR, f"{_sanitize_serial(serial)}.json")


def archive_dir_for(serial: Optional[str]) -> str:
    return os.path.join(_ARCHIVE_ROOT, _sanitize_serial(serial))


def list_existing_serials() -> List[str]:
    """扫描 ``data/friends/`` 下已存在的 serial 列表（用于退出时归档）。"""
    if not os.path.isdir(_FRIENDS_DIR):
        return []
    out: List[str] = []
    for name in os.listdir(_FRIENDS_DIR):
        if not name.endswith(".json"):
            continue
        out.append(name[:-5])
    return out


# ---------------------------------------------------------------------------
# 进程级 serial → StorageHandler 单例缓存
# 避免同一设备的多个组件（pipeline / chatter / actions）各自构造导致锁失效
# ---------------------------------------------------------------------------
_HANDLERS_LOCK = threading.Lock()
_HANDLERS: Dict[str, "StorageHandler"] = {}


def get_storage_for(serial: Optional[str]) -> "StorageHandler":
    """工厂方法：同一 serial 返回同一个 StorageHandler 实例。"""
    key = _sanitize_serial(serial)
    with _HANDLERS_LOCK:
        h = _HANDLERS.get(key)
        if h is None:
            h = StorageHandler(serial=serial)
            _HANDLERS[key] = h
        return h


class StorageHandler:
    """好友库 JSON 读写，线程安全。

    好友条目 schema（向后兼容旧的空 `{}`）::

        {
          "<uid>": {
            "uid": "...", "name": "...",
            "status": "pending|accepted|replied|mutual|pending_followback|failed",
            "round": 1,
            "last_action_at": "ISO8601",
            "last_message": "...",
            "notes": "",
            "awaiting_peer_after_first_outbound": false,
            "peer_replied_to_first": false,
            "post_topbar_mutual_probe_pending": false,
            "huiguan_sent": false
          }
        }
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        serial: Optional[str] = None,
    ) -> None:
        # 路径解析优先级：
        #   1. 显式 serial → data/friends/<serial>.json
        #   2. 显式 file_path（兼容旧调用）
        #   3. 默认 → data/friends/default.json
        if serial is not None:
            self.serial: str = _sanitize_serial(serial)
            self.file_path: str = friends_path_for(serial)
        elif file_path is not None:
            self.file_path = file_path
            # 反推 serial（用于归档目录）：若就是 legacy `data/friends.json` 则 default
            if os.path.abspath(file_path) == os.path.abspath(_LEGACY_PATH):
                self.serial = _DEFAULT_SERIAL
            else:
                base = os.path.basename(file_path)
                self.serial = base[:-5] if base.endswith(".json") else _DEFAULT_SERIAL
        else:
            self.serial = _DEFAULT_SERIAL
            self.file_path = friends_path_for(None)

        self._lock = threading.RLock()
        parent = os.path.dirname(self.file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(self.file_path):
            self._write_all({})

    # ------------------------------------------------------------------
    # 工厂
    # ------------------------------------------------------------------
    @classmethod
    def for_serial(cls, serial: Optional[str]) -> "StorageHandler":
        return get_storage_for(serial)

    # ------------------------------------------------------------------
    # IO 内部
    # ------------------------------------------------------------------
    def _read_all(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except FileNotFoundError:
            return {}
        except Exception:
            logging.exception("%s 读取失败，视为空库", self.file_path)
            return {}

    def _write_all(self, friends: Dict[str, Dict[str, Any]]) -> None:
        tmp = f"{self.file_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(friends, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)

    # ------------------------------------------------------------------
    # 安全退出：归档 + 清零
    # ------------------------------------------------------------------
    def archive_and_clear(self, *, keep_last: int = _MAX_ARCHIVES_PER_SERIAL) -> Optional[str]:
        """把当前 friends json 归档后写回 ``{}``。

        - 归档路径：``data/archive/friends/<serial>/friends.<YYYYMMDD-HHMMSS>.json``
        - 仅当文件存在且非空（>2 字节，避开 `{}`）时归档；
        - 自动滚动删除超过 ``keep_last`` 份的旧归档；
        - 返回归档文件路径（若实际归档了）或 None。
        """
        with self._lock:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            archived: Optional[str] = None
            try:
                if os.path.exists(self.file_path) and os.path.getsize(self.file_path) > 2:
                    arc_dir = archive_dir_for(self.serial)
                    os.makedirs(arc_dir, exist_ok=True)
                    archived = os.path.join(arc_dir, f"friends.{ts}.json")
                    shutil.copy2(self.file_path, archived)
                    self._write_all({})
                    # 滚动清理
                    try:
                        files = sorted(
                            (
                                os.path.join(arc_dir, n)
                                for n in os.listdir(arc_dir)
                                if n.startswith("friends.") and n.endswith(".json")
                            ),
                            reverse=True,
                        )
                        for old in files[keep_last:]:
                            try:
                                os.remove(old)
                            except OSError:
                                pass
                    except Exception:
                        logging.exception("清理旧归档失败（忽略）: %s", arc_dir)
                else:
                    # 文件不存在或空 → 直接确保空 JSON 存在
                    self._write_all({})
            except Exception:
                logging.exception("archive_and_clear 失败: %s", self.file_path)
            return archived

    # ------------------------------------------------------------------
    # 公共 API（保持原签名）
    # ------------------------------------------------------------------
    def get_all_friends(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return self._read_all()

    def get_friend(self, uid: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read_all().get(uid)

    def resolve_friend(
        self, uid: str, name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """按 uid 或列表昵称解析 ``friends.json`` 条目。

        返回 ``(canonical_uid, entry)``；未命中时 ``(None, None)``。
        """
        uid_key = (uid or "").strip()
        display = (name or "").strip()
        with self._lock:
            friends = self._read_all()
        if uid_key and uid_key in friends:
            return uid_key, friends[uid_key]
        for label in (display, uid_key):
            if not label:
                continue
            for fid, entry in friends.items():
                fname = (entry.get("name") or fid or "").strip()
                if not fname or fname == "unknown":
                    continue
                if label in fname or fname in label:
                    return fid, entry
        return None, None

    def update_friend(self, uid: str, data: Dict[str, Any]) -> None:
        """整条覆盖写（保留旧 API）。"""
        with self._lock:
            friends = self._read_all()
            friends[uid] = data
            self._write_all(friends)

    def upsert(self, uid: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """合并写：不覆盖未提供的字段。返回合并后的完整条目。"""
        with self._lock:
            friends = self._read_all()
            base = friends.get(uid) or {"uid": uid}
            base.update({k: v for k, v in patch.items() if v is not None})
            base["uid"] = uid
            friends[uid] = base
            self._write_all(friends)
            return base

    def mark_status(
        self,
        uid: str,
        status: str,
        round_: Optional[int] = None,
        last_message: Optional[str] = None,
        name: Optional[str] = None,
        chat_round: Optional[int] = None,
    ) -> Dict[str, Any]:
        if status not in ALLOWED_STATUS:
            raise ValueError(f"非法 status: {status}")
        patch: Dict[str, Any] = {
            "status": status,
            "last_action_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if round_ is not None:
            patch["round"] = int(round_)
        if last_message is not None:
            patch["last_message"] = last_message
        if name is not None:
            patch["name"] = name
        if chat_round is not None:
            patch["chat_round"] = int(chat_round)
        return self.upsert(uid, patch)

    def bump_reply_count(self, uid: str) -> int:
        """累加并持久化某好友被本工具回复的轮数，返回累加后的值。"""
        with self._lock:
            friends = self._read_all()
            base = friends.get(uid) or {"uid": uid}
            try:
                cur = int(base.get("reply_count") or 0)
            except (TypeError, ValueError):
                cur = 0
            cur += 1
            base["reply_count"] = cur
            base["uid"] = uid
            base["last_action_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            friends[uid] = base
            self._write_all(friends)
            return cur

    def mark_huiguan_sent(self, uid: str) -> Dict[str, Any]:
        """标记已发送过"回关"消息。"""
        return self.upsert(uid, {"huiguan_sent": True})

    def mark_stage2_played(self, uid: str) -> Dict[str, Any]:
        """标记阶段二步骤 1（猜拳+送花）已完成。"""
        return self.upsert(uid, {"stage2_played": True})

    def mark_stage2_replied_handled(self, uid: str, round_: int) -> Dict[str, Any]:
        """标记阶段二步骤 2 处理过的轮次（用于不重不漏）。"""
        return self.upsert(uid, {"stage2_replied_handled_round": int(round_)})

    def get_reply_pool_round(self, uid: str) -> int:
        """读取第一阶段个人消息池进度；0 表示尚未发送池 1。"""
        try:
            entry = self.get_friend(uid) or {}
            value = int(entry.get("reply_pool_round") or 0)
            return max(0, value)
        except (TypeError, ValueError):
            return 0
        except Exception:
            logging.exception("get_reply_pool_round 异常 uid=%s", uid)
            return 0

    def mark_reply_pool_round(self, uid: str, pool_round: int) -> Dict[str, Any]:
        """标记第一阶段已给该好友发送到第几个消息池。"""
        return self.upsert(uid, {"reply_pool_round": max(0, int(pool_round))})

    def increment_chat_round(self, uid: str) -> int:
        """将该好友的 chat_round 加 1，返回新值。"""
        with self._lock:
            friends = self._read_all()
            entry = friends.get(uid) or {"uid": uid}
            cur = int(entry.get("chat_round") or 0)
            cur += 1
            entry["chat_round"] = cur
            entry["uid"] = uid
            entry["last_action_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            friends[uid] = entry
            self._write_all(friends)
            return cur

    def rename_uid(self, old_uid: str, new_uid: str) -> bool:
        """重命名好友的 uid（key）。同时更新条目内的 uid 字段。"""
        with self._lock:
            friends = self._read_all()
            if old_uid not in friends:
                return False
            if new_uid in friends and new_uid != old_uid:
                # 合并：新 uid 已存在，保留旧条目的数据，覆盖 name 等字段
                friends[new_uid].update(friends[old_uid])
                del friends[old_uid]
            else:
                friends[new_uid] = friends.pop(old_uid)
            friends[new_uid]["uid"] = new_uid
            self._write_all(friends)
            return True

    def count_by_status(self) -> Dict[str, int]:
        counters = {s: 0 for s in ALLOWED_STATUS}
        counters["total"] = 0
        with self._lock:
            friends = self._read_all()
        for entry in friends.values():
            if not isinstance(entry, dict):
                continue
            counters["total"] += 1
            st = entry.get("status")
            if st in counters:
                counters[st] += 1
        return counters

    def list_friends(
        self,
        status: Optional[str] = None,
        round_: Optional[int] = None,
    ) -> list:
        with self._lock:
            friends = self._read_all()
        out = []
        for uid, entry in friends.items():
            if not isinstance(entry, dict):
                continue
            if status and entry.get("status") != status:
                continue
            if round_ is not None and int(entry.get("round") or 0) != int(round_):
                continue
            item = dict(entry)
            item.setdefault("uid", uid)
            out.append(item)
        out.sort(key=lambda x: x.get("last_action_at") or "", reverse=True)
        return out


# ---------------------------------------------------------------------------
# 进程级聚合工具（供 server 退出钩子调用）
# ---------------------------------------------------------------------------
def archive_and_clear_all(*, include_unloaded: bool = True) -> Dict[str, Optional[str]]:
    """对所有已知 serial 调用 ``archive_and_clear``。

    - 已构造的 ``StorageHandler`` 单例直接调；
    - 若 ``include_unloaded=True``，再扫 ``data/friends/`` 下其他孤儿文件并归档。
    返回 {serial: archived_path or None}。
    """
    results: Dict[str, Optional[str]] = {}
    with _HANDLERS_LOCK:
        handlers = list(_HANDLERS.values())
    seen: set = set()
    for h in handlers:
        results[h.serial] = h.archive_and_clear()
        seen.add(h.serial)

    if include_unloaded:
        for serial in list_existing_serials():
            if serial in seen:
                continue
            try:
                h = get_storage_for(serial)
                results[serial] = h.archive_and_clear()
            except Exception:
                logging.exception("归档孤儿 storage 失败: %s", serial)
                results[serial] = None
    return results


def aggregate_count_by_status() -> Dict[str, int]:
    """汇总所有 per-device friends 的状态计数（供全局 stats API）。"""
    counters = {s: 0 for s in ALLOWED_STATUS}
    counters["total"] = 0
    for serial in list_existing_serials():
        try:
            h = get_storage_for(serial)
            sub = h.count_by_status()
        except Exception:
            continue
        for k, v in sub.items():
            counters[k] = counters.get(k, 0) + int(v)
    return counters

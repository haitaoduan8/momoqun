import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple


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


class StorageHandler:
    """好友库 JSON 读写，线程安全。

    好友条目 schema（向后兼容旧的空 `{}`）:
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

    def __init__(self, file_path: str = "data/friends.json") -> None:
        self.file_path = file_path
        self._lock = threading.RLock()
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(file_path):
            self._write_all({})

    def _read_all(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except Exception:
            logging.exception("friends.json 读取失败，视为空库")
            return {}

    def _write_all(self, friends: Dict[str, Dict[str, Any]]) -> None:
        tmp = f"{self.file_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(friends, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)

    # ------- 公共 API -------
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

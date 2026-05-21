"""聊天顶栏加好友/通过条：收键盘、点「通过」或「关注」，并写入 friends.json。"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Optional

from actions.config_loader import chat_topbar_friend_config
from core.driver import DeviceHandler
from data.storage import StorageHandler

TEXT_PASS = "通过"
TEXT_FOLLOW = "关注"


def handle_chat_topbar_friend_actions(
    driver: DeviceHandler,
    elements: Dict[str, Any],
    storage: StorageHandler,
    *,
    uid: str,
    name: Optional[str] = None,
    round_id: int,
    bus: Optional[Any] = None,
) -> str:
    """
    若软键盘展开则先 back；再检测 topbar 上「通过」/「关注」并点击、写库。

    返回: ``none`` | ``clicked_pass`` | ``clicked_follow`` | ``error``
    """
    cfg = chat_topbar_friend_config(elements)
    top_rid = cfg.get("topbar_button") or ""
    input_rid = cfg.get("input_box") or ""

    if not top_rid:
        logging.warning("chat_topbar_friend: 未配置 topbar_button")
        return "error"

    def _sleep() -> None:
        d = (driver.settings.get("delay") or {}) if driver.settings else {}
        lo = float(d.get("min", 0.3))
        hi = float(d.get("max", 1.0))
        time.sleep(random.uniform(lo, hi))

    def _publish_log(msg: str) -> None:
        if bus is None:
            return
        try:
            bus.publish_threadsafe("log", {"level": "INFO", "message": msg})
        except Exception:
            logging.debug("chat_topbar_friend: publish log 失败", exc_info=True)

    try:
        if driver.is_keyboard_shown(input_box_rid=input_rid or None):
            try:
                driver.d.press("back")
                _sleep()
                driver.wait_ui_stable(max_wait=1.5, poll=0.12)
            except Exception:
                logging.exception("chat_topbar_friend: 收键盘 back 失败")

        el_pass = driver.d(resourceId=top_rid, text=TEXT_PASS)
        el_follow = driver.d(resourceId=top_rid, text=TEXT_FOLLOW)

        if el_pass.exists:
            if not driver.click_uielement(el_pass):
                logging.warning("chat_topbar_friend: 点击通过失败 uid=%s", uid)
                return "error"
            _sleep()
            try:
                entry = storage.mark_status(
                    uid,
                    "mutual",
                    round_=round_id,
                    last_message="[topbar:pass]",
                    name=name,
                )
                if bus is not None:
                    bus.publish_threadsafe("friend_update", entry)
                _publish_log(f"顶栏已点「通过」→互关: {name or uid}")
            except Exception:
                logging.exception("chat_topbar_friend: 记录 mutual 失败 uid=%s", uid)
                return "error"
            return "clicked_pass"

        if el_follow.exists:
            if not driver.click_uielement(el_follow):
                logging.warning("chat_topbar_friend: 点击关注失败 uid=%s", uid)
                return "error"
            _sleep()
            try:
                entry = storage.mark_status(
                    uid,
                    "pending_followback",
                    round_=round_id,
                    last_message="[topbar:follow]",
                    name=name,
                )
                if bus is not None:
                    bus.publish_threadsafe("friend_update", entry)
                _publish_log(f"顶栏已点「关注」→待回关: {name or uid}")
            except Exception:
                logging.exception("chat_topbar_friend: 记录 pending_followback 失败 uid=%s", uid)
                return "error"
            return "clicked_follow"

        return "none"
    except Exception:
        logging.exception("chat_topbar_friend: 处理异常 uid=%s", uid)
        return "error"

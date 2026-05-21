"""聊天页互关好友识别。

规则：在聊天界面点击左下角语音按钮后，如果出现「按住说话」的语音面板，
则判定当前会话对象为互关好友。所有点击走 DeviceHandler 的随机偏移与随机延迟。
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET

from actions.config_loader import chat_mutual_friend_config
from actions.ui_hierarchy import _parse_bounds, _safe_dump_hierarchy

STATUS_MUTUAL = "mutual"
STATUS_NOT_MUTUAL = "not_mutual"
STATUS_UNKNOWN = "unknown"


@dataclass
class MutualFriendStatus:
    """当前聊天页互关识别结果。"""

    status: str
    reason: str = ""
    voice_button_bounds: Optional[Dict[str, int]] = None
    audio_panel_bounds: Optional[Dict[str, int]] = None
    hold_to_talk_text: Optional[str] = None

    @property
    def is_mutual(self) -> bool:
        return self.status == STATUS_MUTUAL


def _random_delay(driver: Any, min_s: float = 0.2, max_s: float = 0.6) -> None:
    try:
        delay_cfg = (driver.settings.get("delay") or {}) if getattr(driver, "settings", None) else {}
        lo = float(delay_cfg.get("min", min_s))
        hi = float(delay_cfg.get("max", max_s))
        time.sleep(random.uniform(min(lo, hi), max(lo, hi)))
    except Exception:
        logging.debug("mutual_friend_status: 随机延迟异常", exc_info=True)


def _node_bounds(root: ET.Element, resource_id: str) -> Optional[Dict[str, int]]:
    try:
        if not resource_id:
            return None
        for node in root.iter("node"):
            if node.attrib.get("resource-id") == resource_id:
                return _parse_bounds(node.attrib.get("bounds", ""))
    except Exception:
        logging.exception("mutual_friend_status: 查找 bounds 异常 rid=%s", resource_id)
    return None


def _text_exists(root: ET.Element, text: str) -> bool:
    try:
        if not text:
            return False
        for node in root.iter("node"):
            if (node.attrib.get("text") or "").strip() == text:
                return True
    except Exception:
        logging.exception("mutual_friend_status: 查找文本异常 text=%s", text)
    return False


def _has_audio_panel(root: ET.Element, audio_panel_rid: str, hold_text: str) -> bool:
    try:
        return bool(
            (audio_panel_rid and _node_bounds(root, audio_panel_rid) is not None)
            or _text_exists(root, hold_text)
        )
    except Exception:
        logging.exception("mutual_friend_status: 判断语音面板异常")
        return False


def _dump_root(driver: Any) -> Optional[ET.Element]:
    try:
        xml = _safe_dump_hierarchy(driver)
        if not xml:
            return None
        return ET.fromstring(xml)
    except Exception:
        logging.exception("mutual_friend_status: dump/parse hierarchy 异常")
        return None


def _click_voice_button(driver: Any, voice_button_rid: str) -> bool:
    try:
        if not voice_button_rid:
            logging.warning("mutual_friend_status: 未配置 voice_button.resourceId")
            return False
        if not driver.random_click(voice_button_rid):
            logging.warning("mutual_friend_status: 点击语音按钮失败 rid=%s", voice_button_rid)
            return False
        _random_delay(driver)
        try:
            driver.wait_ui_stable(max_wait=1.0, poll=0.12)
        except Exception:
            logging.debug("mutual_friend_status: wait_ui_stable 异常", exc_info=True)
        return True
    except Exception:
        logging.exception("mutual_friend_status: 点击语音按钮异常 rid=%s", voice_button_rid)
        return False


def detect_mutual_friend_by_voice_button(
    driver: Any,
    elements: Dict[str, Any],
    *,
    restore_text_mode: bool = False,
) -> MutualFriendStatus:
    """点击语音按钮识别当前聊天对象是否互关。

    ``restore_text_mode`` 为 True 时，如果本函数确实点击打开了语音面板，会再次点击语音按钮
    尝试恢复文本输入模式。
    """
    clicked = False
    try:
        cfg = chat_mutual_friend_config(elements)
        voice_button_rid = (cfg.get("voice_button") or "").strip()
        audio_panel_rid = (cfg.get("audio_panel") or "").strip()
        hold_text = (cfg.get("hold_to_talk_text") or "").strip()

        root = _dump_root(driver)
        if root is None:
            return MutualFriendStatus(status=STATUS_UNKNOWN, reason="dump_failed")

        voice_bounds = _node_bounds(root, voice_button_rid)
        if voice_bounds is None:
            return MutualFriendStatus(status=STATUS_UNKNOWN, reason="voice_button_missing")

        if _has_audio_panel(root, audio_panel_rid, hold_text):
            return MutualFriendStatus(
                status=STATUS_MUTUAL,
                reason="audio_panel_visible",
                voice_button_bounds=voice_bounds,
                audio_panel_bounds=_node_bounds(root, audio_panel_rid),
                hold_to_talk_text=hold_text,
            )

        clicked = _click_voice_button(driver, voice_button_rid)
        if not clicked:
            return MutualFriendStatus(
                status=STATUS_UNKNOWN,
                reason="voice_button_click_failed",
                voice_button_bounds=voice_bounds,
            )

        root = _dump_root(driver)
        if root is None:
            return MutualFriendStatus(
                status=STATUS_UNKNOWN,
                reason="dump_after_click_failed",
                voice_button_bounds=voice_bounds,
            )

        audio_bounds = _node_bounds(root, audio_panel_rid)
        if _has_audio_panel(root, audio_panel_rid, hold_text):
            return MutualFriendStatus(
                status=STATUS_MUTUAL,
                reason="audio_panel_after_click",
                voice_button_bounds=voice_bounds,
                audio_panel_bounds=audio_bounds,
                hold_to_talk_text=hold_text,
            )

        return MutualFriendStatus(
            status=STATUS_NOT_MUTUAL,
            reason="audio_panel_not_visible",
            voice_button_bounds=voice_bounds,
        )
    except Exception:
        logging.exception("mutual_friend_status: 识别互关状态异常")
        return MutualFriendStatus(status=STATUS_UNKNOWN, reason="exception")
    finally:
        if restore_text_mode and clicked:
            try:
                cfg = chat_mutual_friend_config(elements)
                voice_button_rid = (cfg.get("voice_button") or "").strip()
                _click_voice_button(driver, voice_button_rid)
            except Exception:
                logging.debug("mutual_friend_status: 恢复文本模式失败", exc_info=True)

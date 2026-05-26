"""聊天列表右侧红色未读数字角标检测。

陌陌未读数控件：``com.immomo.momo:id/chatlist_item_tv_status_new``。
仅判断「是否有未读」（节点是否存在），不解析具体数字。
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

from actions.ui_hierarchy import _parse_bounds


def _get_rid(elements: Dict[str, Any], *path: str) -> str:
    node: Any = elements or {}
    for key in path:
        if not isinstance(node, dict):
            return ""
        node = node.get(key)
    if isinstance(node, dict):
        return (node.get("resourceId") or "").strip()
    return ""


def row_has_unread(row_node: ET.Element, badge_rid: str) -> bool:
    """会话行子树内是否存在未读角标节点。"""
    if not badge_rid:
        return False
    try:
        for child in row_node.iter():
            if (child.attrib.get("resource-id") or "") == badge_rid:
                return True
    except Exception:
        logging.exception("chat_unread_badge: row_has_unread 遍历异常")
    return False


def find_friend_with_unread(
    root: ET.Element,
    elements: Dict[str, Any],
    *,
    friend_name: Optional[str] = None,
) -> Optional[str]:
    """查找有未读角标的会话行。

    - ``friend_name`` 有值：仅当该行昵称包含该字符串且存在角标时返回昵称；
    - ``friend_name`` 为空：返回第一个有角标的行昵称。
    """
    row_rid = _get_rid(elements, "chat_list", "chat_row")
    name_rid = _get_rid(elements, "chat_list", "chat_row_name")
    badge_rid = _get_rid(elements, "chat_list", "chat_unread_badge")
    if not row_rid or not badge_rid:
        logging.warning(
            "chat_unread_badge: 缺少 chat_row 或 chat_unread_badge 配置 row=%r badge=%r",
            row_rid,
            badge_rid,
        )
        return None

    target = (friend_name or "").strip()
    try:
        for node in root.iter():
            if node.attrib.get("resource-id") != row_rid:
                continue
            if not row_has_unread(node, badge_rid):
                continue

            row_name = ""
            if name_rid:
                for child in node.iter():
                    if child.attrib.get("resource-id") == name_rid:
                        row_name = (child.attrib.get("text") or "").strip()
                        break

            if target:
                if row_name and target in row_name:
                    return row_name
                continue
            return row_name or None
    except Exception:
        logging.exception(
            "chat_unread_badge: find_friend_with_unread 异常 friend_name=%r",
            friend_name,
        )
    return None


def extract_row_meta(
    row_node: ET.Element,
    elements: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """从 ``item_layout`` 行节点提取 bounds / name / has_unread。"""
    name_rid = _get_rid(elements, "chat_list", "chat_row_name")
    uid_rid = _get_rid(elements, "chat_list", "chat_row_uid")
    badge_rid = _get_rid(elements, "chat_list", "chat_unread_badge")

    bounds = _parse_bounds(row_node.attrib.get("bounds", ""))
    if bounds is None:
        return None

    uid: Optional[str] = None
    name: Optional[str] = None
    for child in row_node.iter():
        rid = child.attrib.get("resource-id") or ""
        if uid_rid and rid == uid_rid and not uid:
            uid = (child.attrib.get("text") or "").strip() or None
        elif name_rid and rid == name_rid and not name:
            name = (child.attrib.get("text") or "").strip() or None

    return {
        "bounds": bounds,
        "name": name,
        "uid": uid,
        "has_unread": row_has_unread(row_node, badge_rid),
    }

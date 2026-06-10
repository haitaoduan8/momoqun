"""换号导入后：返回到微霸手机界面并点击左上角刷新。"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Optional

from core.account_boot import _click_spec, _get_elem_cfg
from utils.helpers import random_delay

_WEIBA_PKG = "com.miui.miuibbs"
_REFRESH_MARKER = "刷新"
_PHONE_SCREEN_MARKER = "分身切换"


def _screen_ready(root: ET.Element) -> bool:
    """是否已在微霸「手机/分身切换」界面（含左上角刷新）。"""
    has_refresh = False
    has_phone_ui = False
    for node in root.iter():
        if node.attrib.get("package") != _WEIBA_PKG:
            continue
        desc = (node.attrib.get("content-desc") or "").strip()
        text = (node.attrib.get("text") or "").strip()
        if _REFRESH_MARKER in desc and node.attrib.get("clickable") == "true":
            has_refresh = True
        if _PHONE_SCREEN_MARKER in text:
            has_phone_ui = True
    return has_refresh and has_phone_ui


def back_to_weiba_phone_and_refresh(
    driver: Any,
    elements: dict,
    settings: dict,
    *,
    logger: Optional[logging.Logger] = None,
    max_backs: int = 2,
) -> bool:
    """连续 back 直到微霸手机界面，再点左上角刷新。"""
    log = logger or logging.getLogger("weiba_refresh")
    elem_cfg = _get_elem_cfg(elements)
    refresh_spec = (elem_cfg.get("weiba") or {}).get("refresh_button") or {
        "contentDesc": "刷新",
        "x": 104,
        "y": 165,
    }

    try:
        for step in range(max_backs + 1):
            try:
                xml = driver.d.dump_hierarchy()
                root = ET.fromstring(xml)
            except Exception:
                log.exception("dump hierarchy 失败 (step=%d)", step)
                root = None

            if root is not None and _screen_ready(root):
                log.info("已回到微霸手机界面，点击刷新")
                if _click_spec(
                    driver, settings, refresh_spec, log, label="weiba_refresh"
                ):
                    random_delay(settings)
                    time.sleep(1.0)
                    return True
                log.warning("刷新按钮点击失败")
                return False

            if step >= max_backs:
                break

            try:
                driver.d.press("back")
                random_delay(settings)
                time.sleep(0.6)
            except Exception:
                log.exception("press back 失败")
                break

        log.warning("未能 back 到微霸手机界面，尝试坐标点击刷新")
        return _click_spec(
            driver, settings, refresh_spec, log, label="weiba_refresh_fallback"
        )
    except Exception:
        log.exception("back_to_weiba_phone_and_refresh 异常")
        return False

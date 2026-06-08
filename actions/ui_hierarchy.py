"""Lightweight helpers for reading Android UI hierarchy XML."""

from __future__ import annotations

import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
import random
from typing import Any, Dict, Optional

BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


class DumpRecoveryFailed(Exception):
    """UI hierarchy dump 重试耗尽，需暂停设备并由上层处理。"""

    def __init__(
        self,
        message: str,
        *,
        serial: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.serial = serial
        self.screenshot_path = screenshot_path
        self.cause = cause


def _parse_bounds(raw_bounds: str) -> Optional[Dict[str, int]]:
    match = BOUNDS_RE.fullmatch(raw_bounds or "")
    if not match:
        return None
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        return None
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
    }


# 与 config/elements.yaml → top_call_ad 对齐
_TOP_CALL_AD_HANG_UP_RID = "com.immomo.momo:id/img_close"
_TOP_CALL_AD_ACCEPT_RID = "com.immomo.momo:id/svga_accept"
_TOP_CALL_AD_TITLE_RID = "com.immomo.momo:id/tv_title"
_TOP_CALL_AD_TITLE_HINT = "打给你"


def detect_top_call_ad(root: ET.Element) -> Optional[Dict[str, int]]:
    """若存在顶部视频来电广告，返回红色挂断按钮 bounds；否则 None。"""
    try:
        hang_bounds: Optional[Dict[str, int]] = None
        has_marker = False
        for node in root.iter():
            rid = node.attrib.get("resource-id") or ""
            if rid == _TOP_CALL_AD_ACCEPT_RID:
                has_marker = True
            if rid == _TOP_CALL_AD_TITLE_RID:
                txt = (node.attrib.get("text") or "").strip()
                if _TOP_CALL_AD_TITLE_HINT in txt:
                    has_marker = True
            if rid != _TOP_CALL_AD_HANG_UP_RID:
                continue
            if node.attrib.get("clickable") != "true":
                continue
            b = _parse_bounds(node.attrib.get("bounds", ""))
            if b and b["top"] < 400:
                hang_bounds = b
        if hang_bounds and has_marker:
            return hang_bounds
        return None
    except Exception:
        logging.exception("detect_top_call_ad 异常")
        return None


def _click_bounds_center(driver: Any, bounds: Dict[str, int]) -> None:
    """带随机偏移点击 bounds 中心（遵守项目点击约定）。"""
    cx = (bounds["left"] + bounds["right"]) // 2
    cy = (bounds["top"] + bounds["bottom"]) // 2
    if hasattr(driver, "random_click_xy"):
        driver.random_click_xy(cx, cy)
        return
    owner = getattr(driver, "_owner", None)
    if owner is not None and hasattr(owner, "random_click_xy"):
        owner.random_click_xy(cx, cy)
        return
    if hasattr(driver, "click"):
        driver.click(cx, cy)
        return
    raise RuntimeError("无法执行带偏移点击：driver 无 random_click_xy/click")


def ensure_hierarchy_without_top_call_ad(
    driver: Any,
    proxy: Any,
    xml: str,
    *,
    compressed: bool = False,
    logger: Optional[logging.Logger] = None,
    max_attempts: int = 3,
) -> str:
    """dump 成功后：若顶部视频来电广告仍在，点挂断并 re-dump 直至消失。"""
    log = logger or logging.getLogger("ui_hierarchy")
    click_driver = driver if driver is not None else proxy

    for attempt in range(max(1, max_attempts)):
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            log.warning("ensure_hierarchy_without_top_call_ad: XML 解析失败")
            return xml

        hang_bounds = detect_top_call_ad(root)
        if hang_bounds is None:
            return xml

        log.info("检测到顶部视频来电广告，点击红色挂断 (attempt %d/%d)", attempt + 1, max_attempts)
        try:
            _click_bounds_center(click_driver, hang_bounds)
        except Exception:
            log.exception("点击顶部广告挂断按钮异常")
            return xml

        time.sleep(random.uniform(0.4, 0.9))
        try:
            if hasattr(proxy, "dump_hierarchy_raw"):
                xml = proxy.dump_hierarchy_raw(compressed=compressed)
            else:
                xml = proxy.dump_hierarchy(compressed=compressed, _skip_ad_clear=True)
        except Exception:
            log.exception("挂断广告后 re-dump 异常")
            return xml

    try:
        if detect_top_call_ad(ET.fromstring(xml)):
            log.warning("多次挂断后顶部视频来电广告仍在")
    except Exception:
        log.debug("挂断后最终检测异常", exc_info=True)
    return xml


def _hierarchy_xml_parseable(xml: str) -> bool:
    if not (xml or "").strip():
        return False
    try:
        ET.fromstring(xml)
        return True
    except ET.ParseError:
        return False


def _dump_failures_dir() -> str:
    """与 momoqun.log 同目录下的 dump_failures/。"""
    for handler in logging.root.handlers:
        if isinstance(handler, logging.FileHandler):
            base = os.path.dirname(os.path.abspath(handler.baseFilename))
            path = os.path.join(base, "dump_failures")
            os.makedirs(path, exist_ok=True)
            return path
    path = os.path.join(os.getcwd(), "dump_failures")
    os.makedirs(path, exist_ok=True)
    return path


def save_failure_screenshot(
    driver: Any,
    serial: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """dump 失败时尝试截图落盘，返回路径或 None。"""
    log = logger or logging.getLogger("ui_hierarchy")
    try:
        pil_im = driver.d.screenshot()
        folder = _dump_failures_dir()
        safe_serial = (serial or "unknown").replace(":", "_").replace("/", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"{safe_serial}_{ts}.png")
        pil_im.save(path)
        log.info("dump 失败截图已保存: %s", path)
        return path
    except Exception:
        log.exception("dump 失败时截图保存异常 serial=%s", serial)
        return None


def dump_hierarchy_with_retry(
    driver: Any,
    *,
    retries: int = 3,
    wait_s: float = 3.0,
    serial: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> str:
    """原地等待并重试 dump；全失败则截图、记日志并抛 DumpRecoveryFailed（不按 back）。"""
    log = logger or logging.getLogger("ui_hierarchy")
    last_exc: Optional[BaseException] = None
    attempts = max(1, int(retries))

    for attempt in range(attempts):
        try:
            xml = driver.d.dump_hierarchy()
            if xml and _hierarchy_xml_parseable(xml):
                return xml
            last_exc = RuntimeError("dump 返回空或非法 XML")
        except Exception as exc:
            last_exc = exc
            log.warning(
                "dump_hierarchy 失败 serial=%s attempt=%d/%d: %s",
                serial, attempt + 1, attempts, exc,
            )
        if attempt + 1 < attempts:
            time.sleep(wait_s)

    screenshot_path = save_failure_screenshot(driver, serial, log)
    msg = f"UI dump {attempts} 次失败"
    if screenshot_path:
        msg += f"；截图: {screenshot_path}"
    log.error("%s (serial=%s)", msg, serial)
    raise DumpRecoveryFailed(
        msg, serial=serial, screenshot_path=screenshot_path, cause=last_exc,
    )


def _safe_dump_hierarchy(driver: Any, retries: int = 2, backoff: float = 0.2) -> Optional[str]:
    """Dump hierarchy with compressed XML first, retrying stale/RPC failures."""
    last_exc: Optional[Exception] = None
    for compressed in (True, False):
        for attempt in range(max(1, retries)):
            try:
                xml = driver.d.dump_hierarchy(compressed=compressed)
                if xml and _hierarchy_xml_parseable(xml):
                    return xml
            except Exception as exc:
                last_exc = exc
                if attempt + 1 < retries:
                    time.sleep(backoff)
                    continue
            if attempt + 1 < retries:
                time.sleep(backoff)
    if last_exc is not None:
        logging.warning("dump_hierarchy 多次失败: %s", last_exc)
        logging.debug("dump_hierarchy 最终异常", exc_info=True)
    return None

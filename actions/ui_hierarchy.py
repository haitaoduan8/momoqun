"""Lightweight helpers for reading Android UI hierarchy XML."""

from __future__ import annotations

import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
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

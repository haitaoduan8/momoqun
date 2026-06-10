"""点击前 dump 并校验当前页面是否符合预期。"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from actions.ui_hierarchy import DumpRecoveryFailed, dump_hierarchy_with_retry

PageSpec = Union[str, Dict[str, Any], None]
Marker = Dict[str, Any]


def _driver_serial(driver: Any) -> Optional[str]:
    serial = getattr(driver, "serial", None)
    if serial:
        return str(serial)
    owner = getattr(getattr(driver, "d", None), "_owner", None)
    if owner is not None:
        s = getattr(owner, "serial", None)
        if s:
            return str(s)
    return None


def _node_matches(node: ET.Element, marker: Marker) -> bool:
    package = (marker.get("package") or "").strip()
    if package and node.attrib.get("package") != package:
        return False

    rid = (marker.get("resourceId") or "").strip()
    if rid and node.attrib.get("resource-id") != rid:
        return False

    text = (marker.get("text") or "").strip()
    if text:
        txt = (node.attrib.get("text") or "").strip()
        partial = bool(marker.get("partial"))
        matched = (text in txt) if partial else (txt == text)
        if not matched:
            return False

    content_desc = (marker.get("contentDesc") or "").strip()
    if content_desc:
        desc = (node.attrib.get("content-desc") or "").strip()
        if content_desc not in desc and desc != content_desc:
            return False

    return True


def hierarchy_has_marker(root: ET.Element, marker: Marker) -> bool:
    """任意节点满足 marker 即视为命中。"""
    if not marker:
        return True
    for node in root.iter():
        if _node_matches(node, marker):
            return True
    return False


def verify_page_on_root(
    root: ET.Element,
    page: PageSpec,
    presets: Optional[Dict[str, Dict[str, Any]]] = None,
) -> bool:
    """根据 page 配置判断当前 hierarchy 是否为预期页面。"""
    if page is None:
        return True
    if isinstance(page, str):
        page = (presets or {}).get(page) or {}
    if not page:
        return True

    for marker in page.get("all") or []:
        if not hierarchy_has_marker(root, marker):
            return False

    any_markers: List[Marker] = page.get("any") or []
    if any_markers and not any(hierarchy_has_marker(root, m) for m in any_markers):
        return False

    for marker in page.get("none") or []:
        if hierarchy_has_marker(root, marker):
            return False

    return True


def dump_hierarchy_root(
    driver: Any,
    *,
    serial: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> Tuple[str, ET.Element]:
    """带重试 dump，返回 (xml, root)。"""
    log = logger or logging.getLogger("page_verify")
    xml = dump_hierarchy_with_retry(
        driver,
        serial=serial or _driver_serial(driver),
        logger=log,
    )
    return xml, ET.fromstring(xml)


def dump_and_verify_page(
    driver: Any,
    page: PageSpec,
    presets: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    serial: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> Optional[Tuple[str, ET.Element]]:
    """dump 后校验页面；不正确或 dump 失败时返回 None（dump 失败抛 DumpRecoveryFailed）。"""
    log = logger or logging.getLogger("page_verify")
    xml, root = dump_hierarchy_root(driver, serial=serial, logger=log)
    if not verify_page_on_root(root, page, presets):
        return None
    return xml, root


def _try_wait_ui_stable(driver: Any, max_wait: float) -> None:
    try:
        driver.wait_ui_stable(max_wait=max_wait)
    except Exception:
        pass


def wait_before_click(
    driver: Any,
    page: PageSpec,
    presets: Optional[Dict[str, Dict[str, Any]]],
    *,
    retries: int = 12,
    poll_s: float = 1.0,
    serial: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    label: str = "",
    element_ready: Optional[Callable[[ET.Element], bool]] = None,
) -> Optional[Tuple[str, ET.Element]]:
    """点击前循环 dump + 页面校验；可选等待目标元素出现。"""
    log = logger or logging.getLogger("page_verify")
    attempts = max(1, int(retries))
    poll = max(0.2, float(poll_s))

    for attempt in range(1, attempts + 1):
        log.info(
            "【点击前 dump】%s 第 %d/%d 次 page=%s",
            label or "-",
            attempt,
            attempts,
            page,
        )
        try:
            verified = dump_and_verify_page(
                driver,
                page,
                presets,
                serial=serial,
                logger=log,
            )
        except DumpRecoveryFailed:
            raise
        except Exception:
            log.exception("【dump 异常】%s", label)
            verified = None

        if verified is None:
            log.warning(
                "【页面未就绪】%s page=%s，%.1fs 后重试",
                label or "-",
                page,
                poll,
            )
            if attempt < attempts:
                time.sleep(poll)
                _try_wait_ui_stable(driver, min(poll, 1.5))
            continue

        _, root = verified
        if element_ready is not None and not element_ready(root):
            log.info(
                "【页面OK 元素未出现】%s，%.1fs 后重试",
                label or "-",
                poll,
            )
            if attempt < attempts:
                time.sleep(poll)
                _try_wait_ui_stable(driver, min(poll, 1.5))
            continue

        log.info("【页面OK】%s 可以执行点击", label or "-")
        return verified

    log.warning("【页面超时】%s page=%s，放弃点击", label or "-", page)
    return None

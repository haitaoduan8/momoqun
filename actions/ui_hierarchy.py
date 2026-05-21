"""Lightweight helpers for reading Android UI hierarchy XML."""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


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

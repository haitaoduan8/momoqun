"""广告/意外页面 XML 收集器。

当脚本遇到非预期页面（弹窗、广告、未知 UI）时，保存完整 hierarchy XML
到 data/ad_pages/ 供后续分析。
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Optional

_LOG = logging.getLogger("ad_collector")

# 输出目录
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_AD_PAGES_DIR = os.path.join(_BASE_DIR, "ad_pages")

# 去重：最近 N 秒内相同指纹不重复保存
_DEDUP_WINDOW_S = 30.0
_recent_fingerprints: dict[str, float] = {}


def _ensure_dir() -> None:
    os.makedirs(_AD_PAGES_DIR, exist_ok=True)


def _fingerprint(xml: str) -> str:
    """取 XML 前 500 字符的 md5 作为页面指纹。"""
    return hashlib.md5(xml[:500].encode("utf-8", errors="replace")).hexdigest()[:12]


def save_ad_page(
    xml: str,
    serial: str = "unknown",
    label: str = "unknown",
    *,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """保存一份意外页面 XML。

    Returns:
        保存的文件路径，或 None（被去重跳过 / xml 为空）。
    """
    log = logger or _LOG
    if not xml or not xml.strip():
        return None

    fp = _fingerprint(xml)
    now = time.time()

    # 去重
    last_seen = _recent_fingerprints.get(fp, 0)
    if now - last_seen < _DEDUP_WINDOW_S:
        log.debug("ad_collector: 去重跳过 fp=%s label=%s", fp, label)
        return None
    _recent_fingerprints[fp] = now

    # 清理过期指纹
    if len(_recent_fingerprints) > 200:
        cutoff = now - _DEDUP_WINDOW_S * 3
        expired = [k for k, v in _recent_fingerprints.items() if v < cutoff]
        for k in expired:
            del _recent_fingerprints[k]

    try:
        _ensure_dir()
        safe_serial = serial.replace(":", "_").replace("/", "_")
        safe_label = label.replace(" ", "_").replace("/", "_")[:40]
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_serial}_{ts}_{safe_label}_{fp}.xml"
        filepath = os.path.join(_AD_PAGES_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(xml)
        log.info("ad_collector: 已保存 %s (%d bytes)", filename, len(xml))
        return filepath
    except Exception:
        log.exception("ad_collector: 保存失败")
        return None


def try_collect_from_driver(
    driver,
    serial: str = "unknown",
    label: str = "unknown",
    *,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """从 driver dump 一次 hierarchy 并保存。方便在异常处理中一行调用。"""
    try:
        xml = driver.d.dump_hierarchy()
    except Exception:
        (logger or _LOG).debug("ad_collector: dump 失败", exc_info=True)
        return None
    return save_ad_page(xml, serial=serial, label=label, logger=logger)

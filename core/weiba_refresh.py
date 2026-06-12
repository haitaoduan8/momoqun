"""换号导入后：返回到微霸手机界面并点击左上角刷新。"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Optional

from core.account_boot import _click_spec, _click_xy, _get_elem_cfg
from utils.helpers import random_delay

_WEIBA_PKG = "com.miui.miuibbs"
_MOMO_PKG = "com.immomo.momo"
_REFRESH_MARKER = "刷新"
_PHONE_SCREEN_MARKER = "分身切换"


def _weiba_fullscreen_webview(root: ET.Element) -> bool:
    """微霸 WebView 占满全屏（浅 dump 时无内部节点），视为可能在目标页。"""
    for node in root.iter():
        if node.attrib.get("package") != _WEIBA_PKG:
            continue
        if node.attrib.get("class") != "android.webkit.WebView":
            continue
        bounds = node.attrib.get("bounds", "")
        try:
            import re
            nums = re.findall(r"\d+", bounds)
            if len(nums) == 4:
                x1, y1, x2, y2 = int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])
                if (x2 - x1) >= 900 and (y2 - y1) >= 2000:
                    return True
        except Exception:
            pass
    return False


def _has_refresh_marker(root: ET.Element) -> bool:
    for node in root.iter():
        if node.attrib.get("package") != _WEIBA_PKG:
            continue
        desc = (node.attrib.get("content-desc") or "").strip()
        if _REFRESH_MARKER in desc and node.attrib.get("clickable") == "true":
            return True
    return False


def _has_phone_ui_marker(root: ET.Element) -> bool:
    for node in root.iter():
        if node.attrib.get("package") != _WEIBA_PKG:
            continue
        text = (node.attrib.get("text") or "").strip()
        if _PHONE_SCREEN_MARKER in text:
            return True
    return False


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
    if has_refresh and has_phone_ui:
        return True
    # 浅 WebView 兜底：WebView 占满全屏时认为可能在目标页
    return _weiba_fullscreen_webview(root)


_LAUNCHER_PKGS = {
    "com.miui.home",
    "com.android.launcher",
    "com.android.launcher3",
    "com.google.android.apps.nexuslauncher",
    "com.huawei.android.launcher",
    "com.samsung.android.launcher",
    "com.oppo.launcher",
    "com.coloros.launcher",
}


def _is_launcher(root: Optional[ET.Element]) -> bool:
    """检测当前是否在桌面（launcher）界面。"""
    if root is None:
        return False
    for node in root.iter():
        pkg = (node.attrib.get("package") or "").strip()
        if pkg in _LAUNCHER_PKGS:
            return True
    return False


def _foreground_package(root: Optional[ET.Element]) -> str:
    if root is None:
        return ""
    for node in root.iter():
        pkg = (node.attrib.get("package") or "").strip()
        if pkg in (_WEIBA_PKG, _MOMO_PKG):
            return pkg
    return ""


def _try_click_refresh(
    driver: Any,
    settings: dict,
    refresh_spec: dict,
    log: logging.Logger,
) -> bool:
    try:
        if _click_spec(driver, settings, refresh_spec, log, label="weiba_refresh"):
            random_delay(settings)
            time.sleep(1.0)
            return True
    except Exception:
        log.warning("_click_spec weiba_refresh 异常，尝试坐标兜底")
    # 坐标兜底：浅 WebView 时页面校验会失败，直接点配置坐标
    x, y = refresh_spec.get("x"), refresh_spec.get("y")
    if x is not None and y is not None:
        log.warning("【坐标兜底】weiba_refresh → (%s, %s)", x, y)
        driver.random_click_xy(int(x), int(y))
        random_delay(settings)
        time.sleep(1.0)
        return True
    return False


def _launch_weiba_from_launcher(
    driver: Any,
    elements: dict,
    settings: dict,
    log: logging.Logger,
) -> None:
    """从桌面坐标进入微霸分身页。"""
    elem_cfg = _get_elem_cfg(elements)
    launcher = elem_cfg.get("launcher") or {}
    weiba = elem_cfg.get("weiba") or {}
    weiba_icon = launcher.get("weiba_icon") or {}
    ix, iy = weiba_icon.get("x"), weiba_icon.get("y")
    if ix is not None and iy is not None:
        log.info("ensure_weiba: 坐标点击桌面微霸 → (%s, %s)", ix, iy)
        _click_xy(
            driver,
            settings,
            int(ix),
            int(iy),
            log,
            page="launcher",
            label="weiba_icon",
        )
    else:
        log.warning("ensure_weiba: weiba_icon 未配置坐标")
    _click_spec(
        driver, settings, weiba.get("fenshen_tab") or {}, log, label="fenshen_tab"
    )
    random_delay(settings)
    time.sleep(0.8)


def ensure_weiba_phone_and_refresh(
    driver: Any,
    elements: dict,
    settings: dict,
    *,
    logger: Optional[logging.Logger] = None,
    max_steps: int = 10,
) -> bool:
    """从陌陌或任意界面回到微霸手机页并点刷新。"""
    log = logger or logging.getLogger("weiba_refresh")
    elem_cfg = _get_elem_cfg(elements)
    refresh_spec = (elem_cfg.get("weiba") or {}).get("refresh_button") or {
        "contentDesc": "刷新",
        "x": 104,
        "y": 165,
    }
    steps = max(3, int(max_steps))

    try:
        launcher_tried = False
        for step in range(steps + 1):
            root = None
            try:
                xml = driver.d.dump_hierarchy()
                root = ET.fromstring(xml)
            except Exception:
                log.exception("ensure_weiba: dump hierarchy 失败 (step=%d)", step)

            # ── 场景 1：已在微霸手机界面 → 点刷新 ──
            if root is not None and _screen_ready(root):
                is_shallow_webview = _weiba_fullscreen_webview(root) and not (
                    _has_refresh_marker(root) and _has_phone_ui_marker(root)
                )
                if is_shallow_webview:
                    log.info("ensure_weiba: 浅 WebView，先点分身 Tab 再刷新")
                    fenshen_spec = (elem_cfg.get("weiba") or {}).get("fenshen_tab") or {
                        "x": 403, "y": 2280,
                    }
                    fx, fy = fenshen_spec.get("x", 403), fenshen_spec.get("y", 2280)
                    log.info("ensure_weiba: 坐标点击分身 Tab → (%s, %s)", fx, fy)
                    driver.random_click_xy(int(fx), int(fy))
                    random_delay(settings)
                    time.sleep(1.5)
                    rx, ry = refresh_spec.get("x", 104), refresh_spec.get("y", 165)
                    log.info("ensure_weiba: 浅 WebView 坐标点击刷新 → (%s, %s)", rx, ry)
                    driver.random_click_xy(int(rx), int(ry))
                    random_delay(settings)
                    time.sleep(1.0)
                    return True
                log.info("ensure_weiba: 已在微霸手机界面，点击刷新")
                if _try_click_refresh(driver, settings, refresh_spec, log):
                    return True
                log.warning("ensure_weiba: 刷新按钮点击失败")
                return False

            if step >= steps:
                break

            fg = _foreground_package(root)

            # ── 场景 2：在陌陌 → Home 回桌面 → 点微霸图标 ──
            if fg == _MOMO_PKG:
                if not launcher_tried:
                    log.info("ensure_weiba: 当前在陌陌，按 Home 回桌面再进微霸")
                    try:
                        driver.d.press("home")
                        random_delay(settings)
                        time.sleep(0.8)
                    except Exception:
                        log.exception("ensure_weiba: press home 失败")
                    launcher_tried = True
                    _launch_weiba_from_launcher(driver, elements, settings, log)
                    continue
                else:
                    log.warning("ensure_weiba: 已在陌陌且尝试过桌面进微霸，按 back 退出")
                    try:
                        driver.d.press("back")
                        random_delay(settings)
                        time.sleep(0.6)
                    except Exception:
                        log.exception("ensure_weiba: press back 失败")
                    continue

            # ── 场景 3：在桌面 → 直接点微霸图标 + 分身 Tab ──
            if _is_launcher(root):
                if not launcher_tried:
                    log.info("ensure_weiba: 当前在桌面，直接点击微霸图标进入")
                    launcher_tried = True
                    _launch_weiba_from_launcher(driver, elements, settings, log)
                    continue
                else:
                    log.warning("ensure_weiba: 已在桌面且尝试过进微霸，仍未成功")
                    break

            # ── 其他未知页面 → 收集广告 + 按 back ──
            try:
                from data.ad_collector import save_ad_page
                if root is not None:
                    save_ad_page(
                        ET.tostring(root, encoding="unicode"),
                        serial=getattr(driver, "serial", ""),
                        label="weiba_unknown_page",
                        logger=log,
                    )
            except Exception:
                pass
            try:
                driver.d.press("back")
                random_delay(settings)
                time.sleep(0.6)
            except Exception:
                log.exception("ensure_weiba: press back 失败")
                break

        log.warning("ensure_weiba: 未能回到微霸手机界面")
        return False
    except Exception:
        log.exception("ensure_weiba_phone_and_refresh 异常")
        return False


def back_to_weiba_phone_and_refresh(
    driver: Any,
    elements: dict,
    settings: dict,
    *,
    logger: Optional[logging.Logger] = None,
    max_backs: int = 2,
) -> bool:
    """连续 back 直到微霸手机界面，再点左上角刷新（兼容旧调用）。"""
    _ = max_backs
    return ensure_weiba_phone_and_refresh(
        driver,
        elements,
        settings,
        logger=logger,
        max_steps=10,
    )

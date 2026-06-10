"""微霸自动上号：桌面点微霸 → 分身切换 → 定位 → 打开陌陌 → 权限（假定启动前已在桌面）。"""

from __future__ import annotations

import enum
import logging
import random
import time
import xml.etree.ElementTree as ET
from typing import Any, Optional

from actions.page_verify import (
    DumpRecoveryFailed,
    dump_and_verify_page,
    hierarchy_has_marker,
    wait_before_click,
)
from utils.helpers import parse_bounds, random_delay


class BootResult(str, enum.Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


class BootStepFailed(Exception):
    """上号单步点击失败（重试耗尽），由上层暂停设备并展示到前端。"""

    def __init__(self, step: str, reason: str) -> None:
        self.step = step
        self.reason = reason
        super().__init__(f"{step}: {reason}")


_DEFAULT_ELEMENTS: dict = {
    "launcher": {
        # 桌面固定槽位，仅坐标点击（用户将微霸图标放于此处）
        "weiba_icon": {"x": 741, "y": 311, "page": "launcher"},
    },
    "weiba": {
        "refresh_button": {
            "contentDesc": "刷新",
            "x": 104,
            "y": 165,
            "page": "weiba_phone",
        },
        "fenshen_tab": {
            "contentDesc": "分身",
            "text": "分身",
            "partial": True,
            "bottom_tab": True,
            "x": 403,
            "y": 2280,
            "page": "weiba",
        },
        "home_tab": {
            "contentDesc": "首页",
            "text": "首页",
            "partial": True,
            "bottom_tab": True,
            "x": 135,
            "y": 2280,
            "page": "weiba",
        },
        "first_clone": {"x": 135, "y": 805, "page": "weiba"},
        "one_key_switch": {
            "text": "一键切换",
            "partial": True,
            "x": 540,
            "y": 2194,
            "page": "weiba_switch_dialog",
        },
        "open_button": {"text": "打开", "partial": True, "x": 539, "y": 550, "page": "weiba"},
        "location_sim": {"text": "位置模拟", "partial": True, "x": 290, "y": 1324, "page": "weiba"},
        "address_input": {"resourceId": "suggestId", "x": 540, "y": 259, "page": "weiba"},
        "done_button": {"text": "完成", "partial": True, "x": 983, "y": 167, "page": "weiba"},
    },
    "momo": {
        "enable_location": {"text": "一键开启", "x": 540, "y": 1381, "page": "momo"},
        "permission_allow": {
            "resourceId": "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
            "text": "使用时允许",
            "partial": True,
            "match_all": False,
            "x": 540,
            "y": 1498,
            "page": "permission",
        },
        "network_dialog_marker": {"text": "网络提示"},
        "network_play": {
            "resourceId": "com.immomo.momo:id/dialog_video_confirm",
            "text": "播放",
            "x": 745,
            "y": 1422,
            "page": {
                "all": [{"package": "com.immomo.momo"}],
                "any": [{"text": "网络提示", "partial": True}],
            },
        },
        "message_tab": {
            "resourceId": "com.immomo.momo:id/maintab_layout_chat",
            "x": 540,
            "y": 2266,
            "page": "momo_main",
        },
        "message_badge": {
            "resourceId": "com.immomo.momo:id/tab_item_tv_badge",
            "x": 579,
            "y": 2222,
            "page": "momo_main",
        },
        "badge_drag_target": {"x": 1050, "y": 300},
        "more_tab": {
            "resourceId": "com.immomo.momo:id/maintab_layout_profile",
            "x": 972,
            "y": 2266,
            "page": "momo_main",
        },
        "post_dynamic_button": {"text": "发动态", "x": 202, "y": 1062, "page": "momo"},
        "post_editor": {
            "resourceId": "com.immomo.momo:id/edit_publish_txt",
            "x": 540,
            "y": 631,
            "page": "momo",
        },
        "post_publish": {
            "resourceId": "com.immomo.momo:id/llayout_send",
            "text": "发布",
            "x": 924,
            "y": 178,
            "page": "momo",
        },
    },
}

# 点击前页面校验预设（spec.page 可引用名称或内联 {all/any/none: [...]}）
_PAGE_PRESETS: dict = {
    "launcher": {
        "none": [
            {"package": "com.immomo.momo"},
            {"package": "com.miui.miuibbs"},
        ],
    },
    "weiba": {
        "all": [{"package": "com.miui.miuibbs"}],
    },
    "weiba_phone": {
        "all": [{"package": "com.miui.miuibbs"}],
        "any": [
            {"contentDesc": "刷新"},
            {"text": "分身切换", "partial": True},
        ],
    },
    "weiba_fenshen": {
        "all": [{"package": "com.miui.miuibbs"}],
        "any": [
            {"text": "一键切换", "partial": True},
            {"text": "分身切换", "partial": True},
            {"text": "检测到", "partial": True},
            {"contentDesc": "分身"},
        ],
    },
    # 弹窗常为 WebView，无障碍树可能只有遮罩+底栏、无按钮文案（见 debug_switch_dialog.xml）
    "weiba_switch_dialog": {
        "all": [{"package": "com.miui.miuibbs"}],
    },
    "momo": {
        "all": [{"package": "com.immomo.momo"}],
    },
    "momo_main": {
        "all": [{"package": "com.immomo.momo"}],
        "any": [
            {"resourceId": "com.immomo.momo:id/maintab_layout_chat"},
            {"resourceId": "com.immomo.momo:id/maintab_layout_profile"},
        ],
    },
    "permission": {
        "any": [
            {
                "resourceId": (
                    "com.android.permissioncontroller:id/"
                    "permission_allow_foreground_only_button"
                ),
            },
            {"text": "使用时允许", "partial": True},
        ],
    },
}


def _get_elem_cfg(elements: dict) -> dict:
    base = {k: dict(v) if isinstance(v, dict) else v for k, v in _DEFAULT_ELEMENTS.items()}
    user = (elements or {}).get("account_boot") or {}
    for section, items in user.items():
        if not isinstance(items, dict):
            base[section] = items
            continue
        sec = dict(base.get(section) or {})
        for name, spec in items.items():
            if isinstance(spec, dict) and isinstance(sec.get(name), dict):
                merged = dict(sec[name])
                merged.update(spec)
                sec[name] = merged
            else:
                sec[name] = spec
        base[section] = sec
    return base


def _step_delay(settings: dict, boot_cfg: dict) -> None:
    wait_s = float(boot_cfg.get("step_wait_s") or 1.5)
    random_delay(settings)
    time.sleep(wait_s)


def _spec_page(spec: dict) -> Any:
    return spec.get("page")


def _page_verify_opts(settings: dict) -> dict:
    boot_cfg = (settings or {}).get("account_boot") or {}
    return {
        "retries": int(boot_cfg.get("page_verify_retries") or 12),
        "poll_s": float(boot_cfg.get("page_verify_poll_s") or 1.0),
    }


def _allow_coord_fallback(settings: dict, spec: dict) -> bool:
    boot_cfg = (settings or {}).get("account_boot") or {}
    if "allow_coord_fallback" in spec:
        return bool(spec.get("allow_coord_fallback"))
    return bool(boot_cfg.get("allow_coord_fallback", True))


def _fail_click(logger: logging.Logger, label: str, reason: str) -> None:
    logger.error("【点击失败】%s — %s", label, reason)
    raise BootStepFailed(label, reason)


def _spec_needs_element(spec: dict) -> bool:
    return bool(
        (spec.get("resourceId") or "").strip()
        or (spec.get("text") or "").strip()
        or (spec.get("contentDesc") or "").strip()
    )


def _after_click_settle(
    driver: Any,
    settings: dict,
    logger: logging.Logger,
    *,
    label: str = "",
) -> None:
    boot_cfg = (settings or {}).get("account_boot") or {}
    try:
        stable_s = float(boot_cfg.get("post_click_stable_s") or 2.0)
        driver.wait_ui_stable(max_wait=stable_s)
    except Exception:
        logger.debug("wait_ui_stable 异常: %s", label, exc_info=True)
    logger.info("【点击后等待】%s 界面稳定 + 步骤间隔", label or "-")
    _step_delay(settings, boot_cfg)


def _click_xy(
    driver: Any,
    settings: dict,
    x: int,
    y: int,
    logger: logging.Logger,
    *,
    page: Any = None,
    label: str = "",
) -> None:
    """坐标点击：循环 dump 直到页面正确，再点击并等待界面稳定。"""
    opts = _page_verify_opts(settings)
    try:
        verified = wait_before_click(
            driver,
            page,
            _PAGE_PRESETS,
            retries=opts["retries"],
            poll_s=opts["poll_s"],
            logger=logger,
            label=label,
        )
        if verified is None:
            _fail_click(
                logger,
                label,
                f"页面未就绪 page={page}（已重试 {opts['retries']} 次）",
            )
        logger.info("【点击】坐标 %s → (%s, %s)", label, x, y)
        driver.random_click_xy(int(x), int(y))
        random_delay(settings)
        _after_click_settle(driver, settings, logger, label=label)
    except BootStepFailed:
        raise
    except DumpRecoveryFailed:
        raise
    except Exception:
        logger.exception("坐标点击失败 %s (%s, %s)", label, x, y)
        _fail_click(logger, label, "点击异常")


def _node_matches_locators(node: ET.Element, spec: dict) -> bool:
    """匹配 resourceId / text / contentDesc；默认任一命中即可（match_all 时全部命中）。"""
    rid = (spec.get("resourceId") or "").strip()
    text = (spec.get("text") or "").strip()
    partial = bool(spec.get("partial"))
    content_desc = (spec.get("contentDesc") or "").strip()
    match_all = bool(spec.get("match_all"))

    checks: list[bool] = []
    if rid:
        checks.append(node.attrib.get("resource-id") == rid)
    if text:
        txt = (node.attrib.get("text") or "").strip()
        checks.append((text in txt) if partial else (txt == text))
    if content_desc:
        desc = (node.attrib.get("content-desc") or "").strip()
        checks.append(content_desc in desc or desc == content_desc)

    if not checks:
        return False
    return all(checks) if match_all else any(checks)


def _log_element_miss_hint(root: ET.Element, spec: dict, logger: logging.Logger, label: str) -> None:
    """页面已通过但元素未命中时，记录 hierarchy 中的相近节点便于排查。"""
    needles = [
        (spec.get("text") or "").strip(),
        (spec.get("contentDesc") or "").strip(),
        (spec.get("resourceId") or "").strip(),
    ]
    needles = [n for n in needles if n]
    if not needles:
        return
    hits: list[str] = []
    for node in root.iter():
        txt = (node.attrib.get("text") or "").strip()
        desc = (node.attrib.get("content-desc") or "").strip()
        rid = node.attrib.get("resource-id") or ""
        for n in needles:
            if n in txt or n in desc or n in rid:
                hits.append(
                    f"text={txt!r} desc={desc!r} rid={rid!r} clickable={node.attrib.get('clickable')}"
                )
                break
        if len(hits) >= 5:
            break
    if hits:
        logger.warning("【元素未命中】%s hierarchy 相近节点: %s", label, " | ".join(hits))
    else:
        logger.warning("【元素未命中】%s hierarchy 中无 text/desc/rid 相近节点", label)


def _weiba_bottom_bar_visible(root: ET.Element) -> bool:
    """微霸底栏容器可见（WebView 浅 dump 时常无「首页/分身」子节点）。"""
    for node in root.iter():
        if node.attrib.get("package") != "com.miui.miuibbs":
            continue
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if bounds is None:
            continue
        x1, y1, x2, y2 = bounds
        if y1 >= 2180 and y2 >= 2340 and (x2 - x1) >= 1000:
            return True
    return False


def _find_first_clone_centroid(root: ET.Element) -> Optional[tuple[int, int]]:
    """分身列表第一个可点文件号（content-desc 为数字 id）。"""
    candidates: list[tuple[int, int, tuple[int, int, int, int]]] = []
    for node in root.iter():
        if node.attrib.get("package") != "com.miui.miuibbs":
            continue
        if node.attrib.get("clickable") != "true":
            continue
        desc = (node.attrib.get("content-desc") or "").strip()
        if not desc.isdigit():
            continue
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if bounds is None:
            continue
        candidates.append((bounds[1], bounds[0], bounds))
    if not candidates:
        return None
    candidates.sort()
    b = candidates[0][2]
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


def _attempt_page_ok_click(
    driver: Any,
    settings: dict,
    spec: dict,
    logger: logging.Logger,
    *,
    label: str,
    page: Any,
    find_target: Optional[Any] = None,
) -> bool:
    """页面已对齐时：优先元素坐标，否则配置坐标兜底。成功返回 True。"""
    try:
        diag = dump_and_verify_page(
            driver, page, _PAGE_PRESETS, logger=logger,
        )
        if diag is None:
            return False
        _, root = diag
        target = find_target(root) if find_target else _find_spec_target(root, spec)
        if target is not None:
            cx, cy = target
            logger.info("【点击】%s → (%s, %s)", label, cx, cy)
            driver.random_click_xy(cx, cy)
            random_delay(settings)
            _after_click_settle(driver, settings, logger, label=label)
            return True
        if _spec_needs_element(spec):
            _log_element_miss_hint(root, spec, logger, label)
        if _coord_click_spec(
            driver,
            settings,
            spec,
            logger,
            label=label,
            reason="页面已就绪但元素未在无障碍树",
        ):
            return True
    except DumpRecoveryFailed:
        raise
    except Exception:
        logger.exception("页面就绪后兜底点击失败: %s", label)
    return False


def _coord_click_spec(
    driver: Any,
    settings: dict,
    spec: dict,
    logger: logging.Logger,
    *,
    label: str = "",
    reason: str = "",
) -> bool:
    if not _allow_coord_fallback(settings, spec):
        return False
    x, y = spec.get("x"), spec.get("y")
    if x is None or y is None:
        return False
    logger.warning(
        "【坐标兜底】%s %s → (%s, %s)",
        label or "-",
        reason or "使用配置坐标",
        x,
        y,
    )
    driver.random_click_xy(int(x), int(y))
    random_delay(settings)
    _after_click_settle(driver, settings, logger, label=label)
    return True


def _find_spec_target(root: ET.Element, spec: dict) -> Optional[tuple[int, int]]:
    candidates: list[tuple[int, int, int, tuple[int, int, int, int]]] = []
    for node in root.iter():
        if not _node_matches_locators(node, spec):
            continue
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if bounds is None:
            continue
        clickable_rank = 0 if node.attrib.get("clickable") == "true" else 1
        candidates.append((clickable_rank, bounds[1], bounds[0], bounds))
    if not candidates:
        return None
    candidates.sort()
    b = candidates[0][3]
    cx = (b[0] + b[2]) // 2
    cy = (b[1] + b[3]) // 2
    return cx, cy


def _click_spec(
    driver: Any,
    settings: dict,
    spec: dict,
    logger: logging.Logger,
    *,
    label: str = "",
) -> None:
    """循环 dump 直到页面与目标元素就绪，再点击；失败抛 BootStepFailed。"""
    page = _spec_page(spec)
    opts = _page_verify_opts(settings)
    need_el = _spec_needs_element(spec)

    def _element_ready(root: ET.Element) -> bool:
        if not need_el:
            return True
        if _find_spec_target(root, spec) is not None:
            return True
        if spec.get("bottom_tab") and _weiba_bottom_bar_visible(root):
            return True
        return False

    try:
        verified = wait_before_click(
            driver,
            page,
            _PAGE_PRESETS,
            retries=opts["retries"],
            poll_s=opts["poll_s"],
            logger=logger,
            label=label,
            element_ready=_element_ready if need_el else None,
        )
        if verified is None:
            if _attempt_page_ok_click(
                driver, settings, spec, logger, label=label, page=page,
            ):
                return
            if verified is None:
                _fail_click(
                    logger,
                    label,
                    f"页面或元素未就绪 page={page}（已重试 {opts['retries']} 次）",
                )
        _, root = verified

        rid = (spec.get("resourceId") or "").strip()
        text = (spec.get("text") or "").strip()
        content_desc = (spec.get("contentDesc") or "").strip()
        target = _find_spec_target(root, spec)
        if target is not None:
            cx, cy = target
            logger.info(
                "【点击】%s → (%s, %s)",
                label or text or rid or content_desc,
                cx,
                cy,
            )
            driver.random_click_xy(cx, cy)
            random_delay(settings)
            _after_click_settle(driver, settings, logger, label=label)
            return

        _log_element_miss_hint(root, spec, logger, label)
        if _coord_click_spec(
            driver,
            settings,
            spec,
            logger,
            label=label,
            reason="元素未命中，使用配置坐标",
        ):
            return
        _fail_click(logger, label, "元素未在 hierarchy 中命中且未启用坐标兜底")
    except BootStepFailed:
        raise
    except DumpRecoveryFailed:
        raise
    except Exception:
        logger.exception("dump/页面校验失败: %s", label)
        _fail_click(logger, label, "点击流程异常")


def _xml_contains(driver: Any, needle: str) -> bool:
    try:
        xml = driver.d.dump_hierarchy()
        return needle in xml
    except Exception:
        return False


def _click_first_clone_slot(
    driver: Any,
    settings: dict,
    spec: dict,
    logger: logging.Logger,
    *,
    label: str = "first_clone",
    reason: str = "",
) -> bool:
    """点击分身列表左上角第一个文件号槽位（固定配置坐标，避免树扫描点到第 2/3 个）。"""
    x, y = spec.get("x"), spec.get("y")
    if x is None or y is None:
        return False
    if reason:
        logger.warning("【坐标兜底】%s %s → (%s, %s)", label, reason, x, y)
    else:
        logger.info("【点击】第一个文件号 → (%s, %s)", x, y)
    driver.random_click_xy(int(x), int(y))
    random_delay(settings)
    _after_click_settle(driver, settings, logger, label=label)
    return True


def _click_first_clone(
    driver: Any,
    settings: dict,
    cfg: dict,
    logger: logging.Logger,
) -> None:
    """第一个文件号：微霸页就绪后点击固定槽位 (135,805)，不依赖无障碍树枚举。"""
    spec = dict((cfg.get("weiba") or {}).get("first_clone") or {})
    page = _spec_page(spec) or "weiba"
    spec["page"] = page
    opts = _page_verify_opts(settings)
    label = "first_clone"

    try:
        verified = wait_before_click(
            driver,
            page,
            _PAGE_PRESETS,
            retries=opts["retries"],
            poll_s=opts["poll_s"],
            logger=logger,
            label=label,
        )
        if verified is not None:
            if _click_first_clone_slot(driver, settings, spec, logger, label=label):
                return
            _fail_click(logger, label, "未配置第一个文件号坐标")

        if _attempt_page_ok_click(
            driver, settings, spec, logger, label=label, page=page,
        ):
            return
        if _allow_coord_fallback(settings, spec) and _click_first_clone_slot(
            driver,
            settings,
            spec,
            logger,
            label=label,
            reason="微霸页未完全识别，仍点击第一个文件号槽位",
        ):
            return
        _fail_click(
            logger,
            label,
            f"微霸分身页未就绪 page={page}（已重试 {opts['retries']} 次）",
        )
    except BootStepFailed:
        raise
    except DumpRecoveryFailed:
        raise
    except Exception:
        logger.exception("点击第一个分身失败")
        _fail_click(logger, label, "点击第一个分身异常")


def _weiba_switch_dialog_visible(root: ET.Element) -> bool:
    """切换确认弹窗：优先文案；WebView 弹窗时仅暴露全屏遮罩 + 底部面板。"""
    for marker in (
        {"text": "一键切换", "partial": True},
        {"text": "修改备注", "partial": True},
        {"text": "修改名称", "partial": True},
        {"text": "删除此环境", "partial": True},
    ):
        if hierarchy_has_marker(root, marker):
            return True

    backdrop = False
    bottom_panel = False
    for node in root.iter():
        if node.attrib.get("package") != "com.miui.miuibbs":
            continue
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if bounds is None:
            continue
        x1, y1, x2, y2 = bounds
        width = x2 - x1
        height = y2 - y1
        cls = node.attrib.get("class") or ""
        text = (node.attrib.get("text") or "").strip()
        if (
            node.attrib.get("clickable") == "true"
            and cls == "android.widget.TextView"
            and not text
            and width >= 1000
            and height >= 1800
        ):
            backdrop = True
        if cls == "android.view.View" and width >= 1000 and y1 >= 1300 and height >= 400:
            bottom_panel = True
    return backdrop and bottom_panel


def _click_one_key_switch(
    driver: Any,
    settings: dict,
    cfg: dict,
    logger: logging.Logger,
) -> None:
    """点文件号后弹窗内点击「一键切换」。"""
    spec = (cfg.get("weiba") or {}).get("one_key_switch") or {}
    page = _spec_page(spec) or "weiba_switch_dialog"
    opts = _page_verify_opts(settings)
    label = "one_key_switch"
    logger.info("等待切换确认弹窗并点击「一键切换」")

    try:
        verified = wait_before_click(
            driver,
            page,
            _PAGE_PRESETS,
            retries=opts["retries"],
            poll_s=opts["poll_s"],
            logger=logger,
            label=label,
            element_ready=_weiba_switch_dialog_visible,
        )
        if verified is None:
            if _attempt_page_ok_click(
                driver, settings, spec, logger, label=label, page=page,
            ):
                return
            x, y = spec.get("x"), spec.get("y")
            if (
                _allow_coord_fallback(settings, spec)
                and x is not None
                and y is not None
            ):
                logger.warning(
                    "【坐标兜底】%s 弹窗未在无障碍树出现，使用配置坐标 → (%s, %s)",
                    label,
                    x,
                    y,
                )
                driver.random_click_xy(int(x), int(y))
                random_delay(settings)
                _after_click_settle(driver, settings, logger, label=label)
                return
            _fail_click(
                logger,
                label,
                f"切换弹窗未出现 page={page}（已重试 {opts['retries']} 次）",
            )
        _, root = verified

        target = _find_spec_target(root, spec)
        if target is not None:
            cx, cy = target
            logger.info("【点击】%s → (%s, %s)", label, cx, cy)
            driver.random_click_xy(cx, cy)
            random_delay(settings)
            _after_click_settle(driver, settings, logger, label=label)
            return

        x, y = spec.get("x"), spec.get("y")
        if x is not None and y is not None:
            logger.warning(
                "【WebView 弹窗】无障碍树无「一键切换」文案，使用配置坐标 (%s, %s)",
                x,
                y,
            )
            driver.random_click_xy(int(x), int(y))
            random_delay(settings)
            _after_click_settle(driver, settings, logger, label=label)
            return

        _fail_click(logger, label, "弹窗已出现但未找到「一键切换」且无坐标配置")
    except BootStepFailed:
        raise
    except DumpRecoveryFailed:
        raise
    except Exception:
        logger.exception("点击一键切换失败")
        _fail_click(logger, label, "点击一键切换异常")


def _select_first_clone_and_switch(
    driver: Any,
    settings: dict,
    elem_cfg: dict,
    boot_cfg: dict,
    logger: logging.Logger,
) -> None:
    """第一个文件号 → 弹窗一键切换 → 等待切换完成。"""
    _click_first_clone(driver, settings, elem_cfg, logger)
    _click_one_key_switch(driver, settings, elem_cfg, logger)
    _clone_select_wait(settings, boot_cfg, logger)


def _type_address(
    driver: Any,
    settings: dict,
    cfg: dict,
    address: str,
    logger: logging.Logger,
) -> None:
    spec = (cfg.get("weiba") or {}).get("address_input") or {}
    _click_spec(driver, settings, spec, logger, label="address_input")
    try:
        driver.human_type(address)
        random_delay(settings)
    except Exception:
        logger.exception("输入预设地址失败")
        _fail_click(logger, "address_input", "输入预设地址失败")


def _dismiss_network_dialog(
    driver: Any,
    settings: dict,
    cfg: dict,
    logger: logging.Logger,
) -> None:
    momo = cfg.get("momo") or {}
    marker = (momo.get("network_dialog_marker") or {}).get("text") or "网络提示"
    if not _xml_contains(driver, marker):
        return
    logger.info("检测到网络提示弹窗，点击播放")
    play_spec = momo.get("network_play") or {}
    _click_spec(driver, settings, play_spec, logger, label="network_play")


def _handle_location_permission(
    driver: Any,
    settings: dict,
    cfg: dict,
    logger: logging.Logger,
) -> None:
    allow_spec = (cfg.get("momo") or {}).get("permission_allow") or {}
    if _xml_contains(driver, "permission_allow_foreground_only_button") or _xml_contains(
        driver, "使用时允许"
    ):
        logger.info("检测到定位权限弹窗")
        _click_spec(driver, settings, allow_spec, logger, label="permission_allow")


def _message_tab_bounds(root: ET.Element) -> Optional[tuple[int, int, int, int]]:
    tab_rid = "com.immomo.momo:id/maintab_layout_chat"
    for node in root.iter():
        if node.attrib.get("resource-id") == tab_rid:
            return parse_bounds(node.attrib.get("bounds", ""))
    return None


def _find_message_tab_badge_xy(
    root: ET.Element,
    badge_spec: dict,
) -> Optional[tuple[int, int]]:
    """只取底部「消息」Tab 上的未读红点，避免误匹配其它 Tab 的 badge。"""
    rid = (badge_spec.get("resourceId") or "").strip()
    if not rid:
        return None
    tab_bounds = _message_tab_bounds(root)
    candidates: list[tuple[int, int, tuple[int, int, int, int]]] = []
    for node in root.iter():
        if node.attrib.get("resource-id") != rid:
            continue
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if bounds is None:
            continue
        cx = (bounds[0] + bounds[2]) // 2
        cy = (bounds[1] + bounds[3]) // 2
        if cy < 2150:
            continue
        if tab_bounds is not None:
            tx1, ty1, tx2, ty2 = tab_bounds
            if not (tx1 <= cx <= tx2 and ty1 <= cy <= ty2):
                continue
        candidates.append((cy, cx, bounds))
    if not candidates:
        return None
    candidates.sort()
    b = candidates[0][2]
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


def _badge_still_on_message_tab(root: ET.Element, badge_spec: dict) -> bool:
    return _find_message_tab_badge_xy(root, badge_spec) is not None


def _badge_drag_timings(settings: dict) -> tuple[int, int]:
    boot_cfg = (settings or {}).get("account_boot") or {}
    try:
        hold_ms = int(boot_cfg.get("badge_drag_hold_ms") or 750)
    except (TypeError, ValueError):
        hold_ms = 750
    try:
        drag_ms = int(boot_cfg.get("badge_drag_swipe_ms") or 2200)
    except (TypeError, ValueError):
        drag_ms = 2200
    return max(100, hold_ms), max(200, drag_ms)


def _perform_badge_drag_gesture(
    driver: Any,
    settings: dict,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    logger: logging.Logger,
    *,
    hold_ms: Optional[int] = None,
    drag_ms: Optional[int] = None,
) -> None:
    co = (settings or {}).get("click_offset") or {}
    ox_max = int(co.get("x") or 5)
    oy_max = int(co.get("y") or 5)
    ox = random.randint(-ox_max, ox_max)
    oy = random.randint(-oy_max, oy_max)
    sx, sy = start_x + ox, start_y + oy
    default_hold, default_drag = _badge_drag_timings(settings)
    hold_ms = default_hold if hold_ms is None else hold_ms
    drag_ms = default_drag if drag_ms is None else drag_ms
    logger.info(
        "拖走消息红点 (%s,%s) → (%s,%s) hold=%sms drag=%sms",
        sx,
        sy,
        end_x,
        end_y,
        hold_ms,
        drag_ms,
    )
    drag_hold = getattr(driver.d, "drag_hold", None)
    if callable(drag_hold):
        drag_hold(sx, sy, end_x, end_y, hold_ms=hold_ms, drag_ms=drag_ms)
    else:
        # 旧版 APK：单次慢滑，避免 long_click + swipe 两次命令中间抬手
        driver.d.swipe(sx, sy, end_x, end_y, max(drag_ms, hold_ms + drag_ms) / 1000.0)
    random_delay(settings)
    time.sleep(0.8)


def _drag_message_badge(
    driver: Any,
    settings: dict,
    cfg: dict,
    logger: logging.Logger,
    *,
    skip_tab_click: bool = False,
) -> None:
    momo = cfg.get("momo") or {}
    tab_spec = momo.get("message_tab") or {}
    badge_spec = momo.get("message_badge") or {}
    target = momo.get("badge_drag_target") or {}

    if not skip_tab_click:
        _click_spec(driver, settings, tab_spec, logger, label="message_tab")

    page = _spec_page(badge_spec) or "momo_main"
    opts = _page_verify_opts(settings)
    try:
        verified = wait_before_click(
            driver,
            page,
            _PAGE_PRESETS,
            retries=opts["retries"],
            poll_s=opts["poll_s"],
            logger=logger,
            label="drag_message_badge",
        )
        if verified is None:
            _fail_click(
                logger,
                "drag_message_badge",
                f"拖红点前页面未就绪 page={page}（已重试 {opts['retries']} 次）",
            )
        _, root = verified
        pos = _find_message_tab_badge_xy(root, badge_spec)
        if pos is None:
            logger.info("消息 Tab 上无未读红点，跳过拖动")
            return
        start_x, start_y = pos
        end_x = int(target.get("x") or 1050)
        end_y = int(target.get("y") or 300)
        hold_ms, drag_ms = _badge_drag_timings(settings)
        max_attempts = 3
        cleared = False
        for attempt in range(1, max_attempts + 1):
            try:
                pos_now = (start_x, start_y)
                if attempt > 1:
                    xml_retry = driver.d.dump_hierarchy()
                    root_retry = ET.fromstring(xml_retry)
                    found = _find_message_tab_badge_xy(root_retry, badge_spec)
                    if found is None:
                        cleared = True
                        break
                    pos_now = found
                attempt_hold = hold_ms + (attempt - 1) * 200
                attempt_drag = drag_ms + (attempt - 1) * 400
                _perform_badge_drag_gesture(
                    driver,
                    settings,
                    pos_now[0],
                    pos_now[1],
                    end_x,
                    end_y,
                    logger,
                    hold_ms=attempt_hold,
                    drag_ms=attempt_drag,
                )
                xml_after = driver.d.dump_hierarchy()
                after_root = ET.fromstring(xml_after)
                if not _badge_still_on_message_tab(after_root, badge_spec):
                    cleared = True
                    logger.info("消息 Tab 红点已拖走（第 %d 次）", attempt)
                    break
                logger.warning(
                    "第 %d/%d 次拖动后红点仍在，%s",
                    attempt,
                    max_attempts,
                    "重试" if attempt < max_attempts else "继续后续步骤",
                )
            except Exception:
                logger.exception("第 %d 次拖走红点手势异常", attempt)
                if attempt >= max_attempts:
                    raise
        if not cleared:
            logger.warning(
                "消息红点未能拖走（已尝试 %d 次），不阻断上号；请确认 Agent APK 已更新并支持 drag_hold",
                max_attempts,
            )
    except BootStepFailed:
        raise
    except DumpRecoveryFailed:
        raise
    except Exception:
        logger.exception("拖走消息红点失败")
        _fail_click(logger, "drag_message_badge", "拖走消息红点失败")


def _clone_select_wait(settings: dict, boot_cfg: dict, logger: logging.Logger) -> None:
    """点击「一键切换」后等待环境切换完成。"""
    try:
        wait_s = float(boot_cfg.get("clone_select_wait_s", 2.0))
    except (TypeError, ValueError):
        wait_s = 2.0
    logger.info("等待文件号切换 %.1fs", wait_s)
    random_delay(settings)
    time.sleep(max(0.0, wait_s))


def _run_weiba_open_momo_tail(
    driver: Any,
    elements: dict,
    settings: dict,
    boot_cfg: dict,
    elem_cfg: dict,
    log: logging.Logger,
) -> BootResult:
    """一键切换之后：首页 → 定位 → 打开陌陌 → 权限/弹窗 → 拖走红点。"""
    weiba = elem_cfg.get("weiba") or {}
    momo = elem_cfg.get("momo") or {}
    preset_address = str(boot_cfg.get("preset_address") or "").strip()

    _click_spec(driver, settings, weiba.get("home_tab") or {}, log, label="weiba_home")
    _click_spec(driver, settings, weiba.get("location_sim") or {}, log, label="location_sim")

    if preset_address:
        _type_address(driver, settings, elem_cfg, preset_address, log)
        _click_spec(driver, settings, weiba.get("done_button") or {}, log, label="done")
    else:
        log.warning("未配置 preset_address，跳过地址输入")

    _click_spec(driver, settings, weiba.get("fenshen_tab") or {}, log, label="fenshen_tab_2")
    _click_spec(driver, settings, weiba.get("open_button") or {}, log, label="open_momo")

    if _xml_contains(driver, "一键开启"):
        _click_spec(driver, settings, momo.get("enable_location") or {}, log, label="enable_location")

    _handle_location_permission(driver, settings, elem_cfg, log)
    _dismiss_network_dialog(driver, settings, elem_cfg, log)
    _drag_message_badge(driver, settings, elem_cfg, log)
    return BootResult.SUCCESS


def run_account_boot_from_phone(
    driver: Any,
    elements: dict,
    settings: dict,
    *,
    logger: Optional[logging.Logger] = None,
) -> BootResult:
    """换号刷新后：已在微霸手机界面，点第一个文件号 → 一键切换 → 打开陌陌…"""
    log = logger or logging.getLogger("account_boot")
    boot_cfg = (settings or {}).get("account_boot") or {}
    elem_cfg = _get_elem_cfg(elements)

    try:
        log.info("换号后续上号：第一个文件号 → 弹窗一键切换 → 打开")
        _select_first_clone_and_switch(driver, settings, elem_cfg, boot_cfg, log)
        result = _run_weiba_open_momo_tail(
            driver, elements, settings, boot_cfg, elem_cfg, log
        )
        if result is BootResult.SUCCESS:
            log.info("换号后续上号完成")
        return result
    except BootStepFailed:
        raise
    except DumpRecoveryFailed:
        raise
    except Exception:
        log.exception("换号后续上号异常")
        return BootResult.FAILED


def run_account_boot(
    driver: Any,
    elements: dict,
    settings: dict,
    *,
    logger: Optional[logging.Logger] = None,
) -> BootResult:
    """执行完整上号流程。"""
    log = logger or logging.getLogger("account_boot")
    boot_cfg = (settings or {}).get("account_boot") or {}
    if not boot_cfg.get("enabled", True):
        log.info("account_boot 未启用，跳过")
        return BootResult.SKIPPED

    elem_cfg = _get_elem_cfg(elements)
    weiba = elem_cfg.get("weiba") or {}
    launcher = elem_cfg.get("launcher") or {}

    try:
        log.info("开始自动上号（假定已在桌面，从点击微霸开始）")
        weiba_icon = launcher.get("weiba_icon") or {}
        ix, iy = weiba_icon.get("x"), weiba_icon.get("y")
        if ix is None or iy is None:
            log.warning("weiba_icon 未配置固定坐标")
            raise BootStepFailed("weiba_icon", "未配置桌面微霸坐标")
        log.info("坐标点击桌面微霸 → (%s, %s)", ix, iy)
        _click_xy(
            driver,
            settings,
            int(ix),
            int(iy),
            log,
            page=_spec_page(weiba_icon) or "launcher",
            label="weiba_icon",
        )
        _click_spec(driver, settings, weiba.get("fenshen_tab") or {}, log, label="fenshen_tab")
        _select_first_clone_and_switch(driver, settings, elem_cfg, boot_cfg, log)

        result = _run_weiba_open_momo_tail(
            driver, elements, settings, boot_cfg, elem_cfg, log
        )
        if result is BootResult.SUCCESS:
            log.info("自动上号完成")
        return result
    except BootStepFailed:
        raise
    except DumpRecoveryFailed:
        raise
    except Exception:
        log.exception("自动上号异常")
        return BootResult.FAILED

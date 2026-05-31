"""账号检测：判断当前设备绑定的陌陌账号是否被风控（异常）。

实现策略
========

直接利用陌陌**个人主页详情页顶部的"账号存在异常"banner**做文本匹配，
完全摆脱图像识别（pHash / 模板匹配 / 灰头像样本采集）。

真机 dump（2026-05-28，1080x2400 / OnePlus 渠道包）确认：
- 异常账号一定会出现该 banner：
  resource-id = ``com.immomo.momo:id/content``
  text       = ``"账号存在异常，点击查看详情"``
- banner 文案"账号存在异常"作为 6 字独特中文短语，
  直接对 ``dump_hierarchy()`` 字符串做 ``in`` 检测即足以精准命中。
- 该方案在 u2_driver / agent_driver 两种通路上行为一致，
  共同依赖项只有 ``driver.d.dump_hierarchy()`` 与 ``driver.d.click()``。

流程
====

  ┌──────────────────────────────────┐
  │ 1. 点底部"更多"tab               │ → maintab_layout_profile
  │ 2. 点左上头像（按屏幕比例坐标）  │ → 进入个人主页详情页
  │ 3. dump hierarchy                │
  │ 4. "账号存在异常" 在 xml 中？    │ → 命中 = ABNORMAL
  │    detail_ready_markers 在 xml？ │ → 仅命中 = OK
  │    都不在                        │ → 等待，超时 = UNKNOWN
  │ 5. press "back" x2 回到主界面    │
  └──────────────────────────────────┘
"""

from __future__ import annotations

import enum
import logging
import time
from typing import Any, Optional


class AccountCheckResult(str, enum.Enum):
    """账号检测结果。继承 str 便于序列化到 JSON / 日志。"""

    OK = "ok"
    ABNORMAL = "abnormal"
    UNKNOWN = "unknown"
    ERROR = "error"

    @property
    def is_abnormal(self) -> bool:
        return self is AccountCheckResult.ABNORMAL


_DEFAULT_ELEMENTS = {
    "more_tab": {"resourceId": "com.immomo.momo:id/maintab_layout_profile"},
    "avatar_xy_ratio": {"x": 0.102, "y": 0.137},
    "abnormal_banner_keyword": "账号存在异常",
    "detail_ready_markers": [
        "com.immomo.momo:id/personal_profile_name",
        "com.immomo.momo:id/toolbar_title",
    ],
    "back_button": {"resourceId": "com.immomo.momo:id/iv_back"},
}


def _get_cfg(elements: dict) -> dict:
    """合并 elements.yaml 中的 account_check 块与默认值。"""
    base = dict(_DEFAULT_ELEMENTS)
    user = (elements or {}).get("account_check") or {}
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merged = dict(base[k])
            merged.update(v)
            base[k] = merged
        else:
            base[k] = v
    return base


def _click_more_tab(driver: Any, cfg: dict, logger: logging.Logger) -> bool:
    """点击底部"更多"tab。优先用 resource-id 精确点击，失败回退到比例坐标。"""
    rid = (cfg.get("more_tab") or {}).get("resourceId") or ""
    try:
        d = driver.d
        # u2 风格 selector 路径（u2_driver 走得通；agent_driver.d 是 proxy
        # 没有 __call__，下面会兜底到坐标点）
        if rid and hasattr(d, "__call__"):
            try:
                el = d(resourceId=rid)
                if el.exists:
                    el.click()
                    return True
            except Exception:
                pass

        # 兜底：dump_hierarchy 找 bounds，自己点
        xml = d.dump_hierarchy()
        if rid and rid in xml:
            bx = _bounds_for_resource_id(xml, rid)
            if bx:
                cx, cy = (bx[0] + bx[2]) // 2, (bx[1] + bx[3]) // 2
                d.click(cx, cy)
                return True

        # 最后兜底：屏幕底部最右 1/5 区域中心
        w, h = d.window_size()
        d.click(int(w * 0.9), int(h * 0.97))
        return True
    except Exception:
        logger.exception("account_check: click more_tab 失败")
        return False


def _click_avatar_top_left(driver: Any, cfg: dict, logger: logging.Logger) -> bool:
    """点左上头像（无 resource-id，使用屏幕比例坐标做跨分辨率适配）。"""
    ratio = cfg.get("avatar_xy_ratio") or {}
    rx = float(ratio.get("x", 0.102))
    ry = float(ratio.get("y", 0.137))
    try:
        w, h = driver.d.window_size()
        driver.d.click(int(w * rx), int(h * ry))
        return True
    except Exception:
        logger.exception("account_check: click avatar 失败")
        return False


def _bounds_for_resource_id(xml: str, rid: str) -> Optional[tuple]:
    """从 dump_hierarchy 的 XML 字符串里粗暴提取目标 resource-id 节点的 bounds。

    返回 (left, top, right, bottom)；找不到返回 None。
    """
    import re

    # 找包含目标 rid 的 node 行，再提其 bounds="[l,t][r,b]"
    pat = re.compile(
        r'resource-id="' + re.escape(rid) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    )
    m = pat.search(xml)
    if not m:
        # 有些 dump bounds 在 resource-id 之前
        pat2 = re.compile(
            r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*resource-id="' + re.escape(rid) + r'"'
        )
        m = pat2.search(xml)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def _press_back(driver: Any, times: int = 1) -> None:
    for _ in range(max(1, times)):
        try:
            driver.d.press("back")
            time.sleep(0.4)
        except Exception:
            pass


def run_account_check(
    driver: Any,
    elements: dict,
    *,
    detect_timeout_sec: float = 8.0,
    logger: Optional[logging.Logger] = None,
) -> AccountCheckResult:
    """对当前设备跑一次账号检测，返回结果。

    入参:
        driver:  ``DeviceHandler`` / ``AgentHandler``，需具备 ``driver.d``
                 暴露 ``dump_hierarchy / click / window_size / press``。
        elements: 已加载的 elements.yaml 字典（顶层）。
        detect_timeout_sec: banner 探测的总超时上限。
        logger:  可选，默认用 "account_check" 子 logger。

    返回:
        ``AccountCheckResult``。调用方负责按 ``on_abnormal`` 策略决定后续行为。
    """
    log = logger or logging.getLogger("account_check")
    cfg = _get_cfg(elements)
    keyword = str(cfg.get("abnormal_banner_keyword") or "账号存在异常")
    markers = list(cfg.get("detail_ready_markers") or [])

    log.info("account_check: 开始")

    # 1) 切到底部"更多"tab
    if not _click_more_tab(driver, cfg, log):
        return AccountCheckResult.ERROR
    try:
        driver.wait_ui_stable(max_wait=1.5)
    except Exception:
        time.sleep(1.2)

    # 2) 点左上头像 → 进入详情页
    if not _click_avatar_top_left(driver, cfg, log):
        # 即便头像点击失败，也尝试 back 让设备回到稳定状态
        _press_back(driver, times=1)
        return AccountCheckResult.ERROR
    try:
        driver.wait_ui_stable(max_wait=2.0)
    except Exception:
        time.sleep(1.8)

    # 3) 等待 banner / detail 标志稳定，最长 detect_timeout_sec
    result = AccountCheckResult.UNKNOWN
    deadline = time.monotonic() + max(1.0, float(detect_timeout_sec))
    last_xml_len = 0
    while time.monotonic() < deadline:
        try:
            xml = driver.d.dump_hierarchy()
        except Exception:
            log.exception("account_check: dump_hierarchy 失败")
            result = AccountCheckResult.ERROR
            break

        # 异常 banner 命中 → 直接定结果
        if keyword and keyword in xml:
            log.warning("account_check: 命中异常 banner '%s'", keyword)
            result = AccountCheckResult.ABNORMAL
            break

        # 已加载到详情页（找到任一锚点）且没有 banner → 正常
        if markers and any(m in xml for m in markers):
            # 详情页已就绪、且无 banner → 判定为 OK
            log.info("account_check: 详情页就绪、无异常 banner -> OK")
            result = AccountCheckResult.OK
            break

        # 还没加载到，xml 长度没变化则可能卡住；继续轮询
        last_xml_len = len(xml)
        time.sleep(0.4)
    else:
        log.warning(
            "account_check: 超时未确认状态（last_xml_len=%d, timeout=%.1fs）",
            last_xml_len, detect_timeout_sec,
        )

    # 4) 清理：返回 2 次让设备回到主聊天列表附近（详情页 → 更多页 → 主页）
    _press_back(driver, times=2)
    try:
        driver.wait_ui_stable(max_wait=1.5)
    except Exception:
        time.sleep(0.8)

    log.info("account_check: 结束，结果=%s", result.value)
    return result

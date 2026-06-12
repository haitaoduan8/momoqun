"""发动态：更多 Tab → 发动态 → 输入文案 → 发布 → 回到消息 Tab。"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from core.account_boot import BootStepFailed, _click_spec, _drag_message_badge, _get_elem_cfg
from utils.helpers import random_delay


def run_post_dynamic(
    driver: Any,
    elements: dict,
    settings: dict,
    *,
    logger: Optional[logging.Logger] = None,
    slot_index: int = 0,
) -> bool:
    """发动态流程。文案从 settings.account_boot.dynamic_contents 按 slot 读取。"""
    log = logger or logging.getLogger("post_dynamic")
    boot_cfg = (settings or {}).get("account_boot") or {}
    if not boot_cfg.get("post_dynamic_enabled", True):
        log.info("post_dynamic 未启用，跳过")
        return False

    # 兼容旧配置：dynamic_content (str) 和 dynamic_contents (list)
    contents = boot_cfg.get("dynamic_contents") or []
    if not contents:
        legacy = str(boot_cfg.get("dynamic_content") or "").strip()
        if legacy:
            contents = [legacy]
    if not contents:
        log.warning("未配置 dynamic_contents，跳过发动态")
        return False
    content = str(contents[slot_index % len(contents)]).strip()
    if not content:
        log.warning("slot %d 的 dynamic_content 为空，跳过发动态", slot_index)
        return False

    elem_cfg = _get_elem_cfg(elements)
    momo = elem_cfg.get("momo") or {}

    try:
        log.info("开始发动态")
        _click_spec(driver, settings, momo.get("more_tab") or {}, log, label="more_tab")
        _click_spec(
            driver, settings, momo.get("post_dynamic_button") or {}, log, label="post_dynamic"
        )
        _click_spec(driver, settings, momo.get("post_editor") or {}, log, label="post_editor")

        try:
            driver.human_type(content)
            random_delay(settings)
        except Exception:
            log.exception("输入动态文案失败")
            raise BootStepFailed("post_editor", "输入动态文案失败") from None

        _click_spec(driver, settings, momo.get("post_publish") or {}, log, label="post_publish")

        time.sleep(float(boot_cfg.get("post_publish_wait_s") or 2.0))

        _click_spec(driver, settings, momo.get("message_tab") or {}, log, label="message_tab_final")
        _drag_message_badge(
            driver, settings, elem_cfg, log, skip_tab_click=True
        )

        log.info("发动态完成，已回到消息页并处理消息红点")
        return True
    except BootStepFailed:
        raise
    except Exception:
        log.exception("发动态异常")
        try:
            from data.ad_collector import try_collect_from_driver
            try_collect_from_driver(driver, serial=getattr(driver, "serial", ""), label="post_dynamic_exc", logger=log)
        except Exception:
            pass
        raise BootStepFailed("post_dynamic", "发动态流程异常") from None

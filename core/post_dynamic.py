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
) -> bool:
    """发动态流程。文案从 settings.account_boot.dynamic_content 读取。"""
    log = logger or logging.getLogger("post_dynamic")
    boot_cfg = (settings or {}).get("account_boot") or {}
    if not boot_cfg.get("post_dynamic_enabled", True):
        log.info("post_dynamic 未启用，跳过")
        return False

    content = str(boot_cfg.get("dynamic_content") or "").strip()
    if not content:
        log.warning("未配置 dynamic_content，跳过发动态")
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
        raise BootStepFailed("post_dynamic", "发动态流程异常") from None

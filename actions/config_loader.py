"""YAML 配置加载与 elements.yaml 的字段解析。"""

import glob
import os

import yaml

DEFAULT_GIFT_ITEM_RID = "com.immomo.momo:id/tv_gift_name"
DEFAULT_GIFT_PAGER_RID = "com.immomo.momo:id/viewpager"


def load_all_yaml(config_dir):
    """扫描 config_dir 下所有 *.yaml / *.yml，返回 {文件名(不含扩展名): 内容 dict}。"""
    configs = {}
    if not os.path.isdir(config_dir):
        raise FileNotFoundError(f"配置目录不存在: {config_dir}")
    paths = sorted(
        glob.glob(os.path.join(config_dir, "*.yaml"))
        + glob.glob(os.path.join(config_dir, "*.yml"))
    )
    for path in paths:
        key = os.path.splitext(os.path.basename(path))[0]
        with open(path, "r", encoding="utf-8") as f:
            configs[key] = yaml.safe_load(f) or {}
    return configs


def gift_entry_config(elements):
    panel = elements.get("gift_panel") or {}
    return panel.get("gift_entry") or {}


def gift_panel_config(elements):
    """返回 (list_rid, item_rid, pager_rid)，缺失字段用默认值兜底。"""
    gp = elements.get("gift_panel") or {}
    list_rid = (gp.get("gift_list") or {}).get("resourceId") or "com.immomo.momo:id/gift_panel_list"
    item_rid = (gp.get("gift_item_name") or {}).get("resourceId") or DEFAULT_GIFT_ITEM_RID
    pager_rid = (gp.get("gift_pager") or {}).get("resourceId") or DEFAULT_GIFT_PAGER_RID
    return list_rid, item_rid, pager_rid


def rose2_target_config(settings):
    """从 settings.yaml 的 config.rose2 读出 (target_row, target_col)。

    缺字段或类型异常时回落默认 (10, 2)，行号下限 1，列号限制在 1~4。
    """
    if not isinstance(settings, dict):
        return 10, 2
    cfg = (settings.get("config") or {}).get("rose2") or {}
    try:
        row = int(cfg.get("target_row", 10))
    except (TypeError, ValueError):
        row = 10
    try:
        col = int(cfg.get("target_col", 2))
    except (TypeError, ValueError):
        col = 2
    row = max(1, row)
    col = max(1, min(4, col))
    return row, col


def chat_topbar_friend_config(elements):
    """返回顶栏与输入框 id，供加好友/通过条使用。"""
    ctf = (elements or {}).get("chat_topbar_friend") or {}
    def _rid(key, fallback_key=None):
        node = ctf.get(key) or (elements.get("buttons", {}).get(fallback_key) if fallback_key else None) or {}
        if isinstance(node, dict):
            return node.get("resourceId") or ""
        return ""
    return {
        "topbar_button": _rid("topbar_button") or "com.immomo.momo:id/topbar_button",
        "topbar_title": _rid("topbar_title") or "com.immomo.momo:id/topbar_title",
        "input_box": _rid("input_box", "input_box") or "com.immomo.momo:id/message_ed_msgeditor",
    }


def chat_message_read_status_config(elements):
    """返回聊天列表消息已读/未读状态图标配置。"""
    elements = elements or {}
    cfg = elements.get("chat_message_read_status") or {}

    def _rid(key, fallback_section=None, fallback_key=None):
        node = cfg.get(key)
        if not isinstance(node, dict) and fallback_section and fallback_key:
            node = (elements.get(fallback_section) or {}).get(fallback_key)
        if isinstance(node, dict):
            return node.get("resourceId") or ""
        return ""

    return {
        "row": _rid("row") or "com.immomo.momo:id/item_layout",
        "name": _rid("name", "chat_list", "chat_row_name")
        or "com.immomo.momo:id/chatlist_item_tv_name",
        "status_icon": _rid("status_icon") or "com.immomo.momo:id/chatlist_item_iv_status",
    }


def chat_mutual_friend_config(elements):
    """返回聊天页互关识别所需控件配置。"""
    elements = elements or {}
    cfg = elements.get("chat_mutual_friend") or {}

    def _node(key, fallback_section=None, fallback_key=None):
        node = cfg.get(key)
        if not isinstance(node, dict) and fallback_section and fallback_key:
            node = (elements.get(fallback_section) or {}).get(fallback_key)
        return node if isinstance(node, dict) else {}

    voice = _node("voice_button")
    audio_panel = _node("audio_panel")
    hold_to_talk = _node("hold_to_talk")
    return {
        "voice_button": voice.get("resourceId") or "com.immomo.momo:id/message_btn_voice",
        "audio_panel": audio_panel.get("resourceId") or "com.immomo.momo:id/ll_audio_btn",
        "hold_to_talk_text": hold_to_talk.get("text") or "按住说话",
    }


def approve_greeting_config(settings, elements):
    """聚合「通过打招呼」模块需要的字段。

    - ``first_batch_size`` 取 settings.yaml 的 ``config.approve_greeting.first_batch_size``，
      兼容旧 ``batch_size``，默认 3，
      负数会被矫正为 0（视为本轮不通过任何一条，仅扫描计数）。
    - ``sayhi_entry_text`` 取 elements.yaml 的 ``entry_elements.sayhi_entry.text``，兜底为「收到的招呼」。
    - ``badge_resource_id`` 取 ``entry_elements.red_dot.resourceId``，用于从 UI 列表页抓未读数字。
    - ``accept_button_resource_id`` 取 ``buttons.accept_button.resourceId``，详情页的「通过」按钮。
    """
    cfg = ((settings or {}).get("config") or {}).get("approve_greeting") or {}
    ee = (elements or {}).get("entry_elements") or {}
    btn = (elements or {}).get("buttons") or {}

    try:
        first_batch_size = int(cfg.get("first_batch_size", cfg.get("batch_size", 3)))
    except (TypeError, ValueError):
        first_batch_size = 3
    first_batch_size = max(0, first_batch_size)

    def _rid(node):
        return node.get("resourceId") if isinstance(node, dict) else ""

    def _text(node):
        return node.get("text") if isinstance(node, dict) else ""

    return {
        "first_batch_size": first_batch_size,
        "batch_size": first_batch_size,
        "sayhi_entry_text": _text(ee.get("sayhi_entry")) or "收到的招呼",
        "badge_resource_id": _rid(ee.get("red_dot")) or "",
        "accept_button_resource_id": _rid(btn.get("accept_button")) or "",
    }


def rock_paper_scissors_config(elements):
    """返回聊天栏「+」面板的猜拳问答入口配置。"""
    elements = elements or {}
    rps = elements.get("rock_paper_scissors") or {}

    def _node(key, fallback_section=None, fallback_key=None):
        node = rps.get(key)
        if not isinstance(node, dict) and fallback_section and fallback_key:
            node = (elements.get(fallback_section) or {}).get(fallback_key)
        return node if isinstance(node, dict) else {}

    more = _node("more_button", "buttons", "more_button")
    entry = _node("entry")
    rematch = _node("rematch")
    return {
        "more_button": more.get("resourceId") or "com.immomo.momo:id/message_btn_more",
        "entry_text": entry.get("text") or "猜拳问答",
        "entry_resource_id": entry.get("resourceId") or "com.immomo.momo:id/chatmenu_tv_name",
        "rematch_text": rematch.get("text") or "再来一局",
        "rematch_resource_id": rematch.get("resourceId") or "com.immomo.momo:id/chat_start_match_text",
        "rematch_container_resource_id": rematch.get("containerResourceId")
        or "com.immomo.momo:id/chat_start_match_pick_small",
    }

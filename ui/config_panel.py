"""配置面板 — Neon Aurora 风格，青色光效表单。"""

import flet as ft
import threading
import requests
from ui.theme import (
    BG_CARD, BG_INPUT, BG_ELEVATED, BG_HOVER, BORDER, BORDER_FOCUS, BORDER_GLOW, DIVIDER,
    TEXT, TEXT_SECONDARY, TEXT_MUTED, TEXT_ACCENT,
    ACCENT, ACCENT_DIM, ACCENT_GLOW, SUCCESS, SUCCESS_DIM, DANGER, DANGER_DIM,
    BTN_RADIUS, CARD_RADIUS, INPUT_RADIUS, ICON_RADIUS,
    accent_btn, outline_btn, form_input, section_title, card_container, separator,
)

API = "http://localhost:5100"
MAX_POOLS = 10


def _form_row(label, ref, val="", hint="", multiline=False, height=44, on_change=None):
    tf = form_input(ref, val, hint, multiline, height, on_change)
    return ft.Container(
        content=ft.Column([
            ft.Text(label, size=12, weight="w600", color=TEXT_SECONDARY),
            tf,
        ], spacing=6),
        padding=ft.padding.only(bottom=14),
    )


def _group_header(text, icon=None):
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(icon, size=18, color=ACCENT) if icon else ft.Container(),
                bgcolor=ACCENT_DIM,
                border_radius=ICON_RADIUS,
                padding=8,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=12,
                    color=ACCENT_GLOW,
                ),
            ) if icon else ft.Container(),
            ft.Text(text, size=13, weight="w700", color=TEXT_ACCENT),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.only(top=18, bottom=14),
    )


class ConfigPanel:
    def __init__(self):
        self.fields: dict[str, ft.Ref[ft.TextField]] = {}
        self.pools: dict[int, ft.Ref[ft.TextField]] = {}
        self.status = ft.Ref[ft.Text]()
        self.pool_count = ft.Ref[ft.TextField]()
        self.strategy = ft.Ref[ft.Dropdown]()
        self.pools_container = ft.Ref[ft.Column]()
        self.direct_mode_switch = ft.Ref[ft.Switch]()
        self._pool_cnt = 5
        self._all_inputs: list = []

        for k in [
            "group_name", "chat_rounds_before_follow", "max_chat_rounds",
            "round_end_wait_s", "chat_round_wait_s", "greet_scan_interval_s",
            "invite_back_message", "max_consecutive_errors",
            "reply_min", "reply_max", "huiguan_message_round",
        ]:
            self.fields[k] = ft.Ref[ft.TextField]()
        for i in range(1, MAX_POOLS + 1):
            self.pools[i] = ft.Ref[ft.TextField]()

    def build(self):
        self._all_inputs = []

        def _make_field(label, ref, val="", hint="", multiline=False, height=44):
            tf = form_input(ref, val, hint, multiline, height)
            self._all_inputs.append(tf)
            return ft.Container(
                content=ft.Column([
                    ft.Text(label, size=12, weight="w600", color=TEXT_SECONDARY),
                    tf,
                ], spacing=6),
                padding=ft.padding.only(bottom=14),
            )

        dm_switch = ft.Switch(
            ref=self.direct_mode_switch,
            value=False,
            active_color=ACCENT,
            on_change=self._on_direct_mode_changed,
        )

        form = ft.Column([
            section_title("运行配置", ft.Icons.SETTINGS),

            ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text("直接拉群模式", size=15, weight="w600", color=TEXT),
                        ft.Text("开启后仅通过招呼→邀请进群→拉黑", size=12, color=TEXT_MUTED),
                    ], spacing=4, expand=True),
                    dm_switch,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=BG_ELEVATED,
                border_radius=CARD_RADIUS,
                padding=ft.padding.symmetric(horizontal=22, vertical=18),
                border=ft.border.all(1, BORDER),
                margin=ft.margin.only(bottom=10),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=20,
                    color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                    offset=ft.Offset(0, 4),
                ),
            ),

            _group_header("群聊设置", ft.Icons.GROUP),
            _make_field("群聊名称", self.fields["group_name"], "我的群聊"),
            _make_field("回关邀请话术", self.fields["invite_back_message"], "互关拉你进群"),

            _group_header("聊天参数", ft.Icons.CHAT_BUBBLE_OUTLINE),
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("聊N轮后关注", size=12, weight="w600", color=TEXT_SECONDARY),
                        form_input(self.fields["chat_rounds_before_follow"], "3", height=42),
                    ], spacing=6), expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("最大聊天轮数", size=12, weight="w600", color=TEXT_SECONDARY),
                        form_input(self.fields["max_chat_rounds"], "10", height=42),
                    ], spacing=6), expand=True,
                ),
            ], spacing=14),
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("回关话术时机(轮)", size=12, weight="w600", color=TEXT_SECONDARY),
                        form_input(self.fields["huiguan_message_round"], "3", hint="设0不发送", height=42),
                    ], spacing=6), expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("最大连续错误", size=12, weight="w600", color=TEXT_SECONDARY),
                        form_input(self.fields["max_consecutive_errors"], "5", height=42),
                    ], spacing=6), expand=True,
                ),
            ], spacing=14),

            _group_header("时间参数", ft.Icons.SCHEDULE),
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("轮次间隔(秒)", size=12, weight="w600", color=TEXT_SECONDARY),
                        form_input(self.fields["round_end_wait_s"], "10", height=42),
                    ], spacing=6), expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("回复等待(秒)", size=12, weight="w600", color=TEXT_SECONDARY),
                        form_input(self.fields["chat_round_wait_s"], "30", height=42),
                    ], spacing=6), expand=True,
                ),
            ], spacing=14),
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("招呼扫描间隔", size=12, weight="w600", color=TEXT_SECONDARY),
                        form_input(self.fields["greet_scan_interval_s"], "5", height=42),
                    ], spacing=6), expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("回复间隔(秒)", size=12, weight="w600", color=TEXT_SECONDARY),
                        ft.Row([
                            form_input(self.fields["reply_min"], "1", height=42),
                            ft.Text("~", size=14, color=TEXT_MUTED, weight="w600"),
                            form_input(self.fields["reply_max"], "3", height=42),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=6), expand=True,
                ),
            ], spacing=14),

            _group_header("聊天策略", ft.Icons.AUTO_AWESOME),
            ft.Container(
                content=ft.Dropdown(
                    ref=self.strategy,
                    value="message_pool",
                    options=[
                        ft.dropdown.Option("message_pool", "消息池模式"),
                        ft.dropdown.Option("ai", "AI 模式（预留）"),
                    ],
                    border_color=BORDER,
                    focused_border_color=BORDER_FOCUS,
                    bgcolor=BG_INPUT,
                    color=TEXT,
                    text_size=13,
                    border_radius=INPUT_RADIUS,
                    content_padding=ft.padding.symmetric(horizontal=18, vertical=14),
                ),
                padding=ft.padding.only(bottom=14),
            ),

            _group_header("消息池", ft.Icons.FORMAT_LIST_BULLETED),
            ft.Container(
                content=ft.Row([
                    ft.Text("数量", size=12, color=TEXT_MUTED, weight="w500"),
                    ft.Container(
                        content=ft.TextField(
                            ref=self.pool_count, value="5", text_size=12,
                            border_color=BORDER, focused_border_color=BORDER_FOCUS,
                            bgcolor=BG_INPUT, color=TEXT,
                            width=56, height=36,
                            content_padding=ft.Padding(left=10, top=0, right=10, bottom=0),
                            text_align="center",
                            border_radius=INPUT_RADIUS,
                            on_change=self._on_pool_count_changed,
                        ),
                        margin=ft.margin.only(left=8, right=8),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=SUCCESS,
                        icon_size=22, tooltip="增加",
                        on_click=self._add_pool,
                        style=ft.ButtonStyle(padding=ft.padding.all(8)),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_color=DANGER,
                        icon_size=22, tooltip="减少",
                        on_click=self._remove_pool,
                        style=ft.ButtonStyle(padding=ft.padding.all(8)),
                    ),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(bottom=10),
            ),

            ft.Column(ref=self.pools_container, spacing=10),

            separator(),
            ft.Row([
                accent_btn("保存配置", self._save, icon=ft.Icons.SAVE, height=44),
                ft.Container(expand=True),
                ft.Text(ref=self.status, size=12, color=TEXT_MUTED, weight="w500"),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

        self._rebuild_pools()

        self._all_inputs.append(self.strategy.current)
        self._all_inputs.append(self.pool_count.current)

        return ft.Container(
            content=form,
            padding=ft.padding.symmetric(horizontal=28, vertical=24),
        )

    def _on_direct_mode_changed(self, e):
        if e is not None:
            enabled = not e.control.value
        else:
            try:
                enabled = not self.direct_mode_switch.current.value
            except Exception:
                enabled = True
        for ctrl in self._all_inputs:
            try:
                ctrl.disabled = not enabled
                ctrl.update()
            except Exception:
                pass
        try:
            self.strategy.current.disabled = not enabled
            self.strategy.current.update()
        except Exception:
            pass

    def _rebuild_pools(self):
        items = []
        for i in range(1, self._pool_cnt + 1):
            label = "池1 — 破冰" if i == 1 else f"池{i}"
            tf = form_input(self.pools[i], multiline=True, height=64)
            self._all_inputs.append(tf)
            items.append(ft.Container(
                content=ft.Column([
                    ft.Text(label, size=12, weight="w600", color=TEXT_SECONDARY),
                    tf,
                ], spacing=6),
                padding=ft.padding.only(bottom=10),
            ))
        try:
            self.pools_container.current.controls = items
            self.pools_container.current.update()
        except Exception:
            pass

    def _on_pool_count_changed(self, e):
        try:
            n = int(self.pool_count.current.value or "5")
            n = max(1, min(n, MAX_POOLS))
            self._pool_cnt = n
            self.pool_count.current.value = str(n)
            self.pool_count.current.update()
            self._rebuild_pools()
        except Exception:
            pass

    def _add_pool(self, e):
        if self._pool_cnt < MAX_POOLS:
            self._pool_cnt += 1
            self.pool_count.current.value = str(self._pool_cnt)
            self.pool_count.current.update()
            self._rebuild_pools()

    def _remove_pool(self, e):
        if self._pool_cnt > 1:
            self.pools[self._pool_cnt].current.value = ""
            self._pool_cnt -= 1
            self.pool_count.current.value = str(self._pool_cnt)
            self.pool_count.current.update()
            self._rebuild_pools()

    def load(self):
        threading.Thread(target=self._ld, daemon=True).start()

    def _ld(self):
        try:
            r = requests.get(f"{API}/api/config", timeout=10)
            cfg = r.json()

            mapping = {
                "group_name": ("group_name", ""),
                "chat_rounds_before_follow": ("chat_rounds_before_follow", "3"),
                "max_chat_rounds": ("max_chat_rounds", "10"),
                "round_end_wait_s": ("round_end_wait_s", "10"),
                "chat_round_wait_s": ("chat_round_wait_s", "30"),
                "greet_scan_interval_s": ("greet_scan_interval_s", "5"),
                "invite_back_message": ("invite_back_message", ""),
                "max_consecutive_errors": ("max_consecutive_errors", "5"),
                "huiguan_message_round": ("huiguan_message_round", "3"),
            }

            for fk, (ck, dv) in mapping.items():
                v = cfg.get(ck, dv)
                if v is not None:
                    self.fields[fk].current.value = str(v)
                    self.fields[fk].current.update()

            dm = cfg.get("direct_group_mode", False)
            self.direct_mode_switch.current.value = bool(dm)
            self.direct_mode_switch.current.update()
            if dm:
                self._on_direct_mode_changed(None)

            ri = cfg.get("reply_interval", {})
            self.fields["reply_min"].current.value = str(ri.get("min", "1"))
            self.fields["reply_min"].current.update()
            self.fields["reply_max"].current.value = str(ri.get("max", "3"))
            self.fields["reply_max"].current.update()

            strat = cfg.get("chat_strategy", "message_pool")
            self.strategy.current.value = strat
            self.strategy.current.update()

            pools = cfg.get("message_pools", [])
            cnt = len(pools) or 5
            self._pool_cnt = max(1, min(cnt, MAX_POOLS))
            self.pool_count.current.value = str(self._pool_cnt)
            self.pool_count.current.update()

            for p in pools:
                pid = p.get("id", 0)
                if 1 <= pid <= MAX_POOLS:
                    self.pools[pid].current.value = "\n".join(p.get("messages", []))
                    self.pools[pid].current.update()

            self._rebuild_pools()
            self._st("加载完成", SUCCESS)
        except Exception as ex:
            self._st(str(ex), DANGER)

    def _save(self, e):
        threading.Thread(target=self._sv, daemon=True).start()

    def _sv(self):
        try:
            cfg = {
                "group_name": self._g("group_name"),
                "chat_rounds_before_follow": int(self._g("chat_rounds_before_follow", "3")),
                "max_chat_rounds": int(self._g("max_chat_rounds", "10")),
                "round_end_wait_s": float(self._g("round_end_wait_s", "10")),
                "chat_round_wait_s": float(self._g("chat_round_wait_s", "30")),
                "greet_scan_interval_s": float(self._g("greet_scan_interval_s", "5")),
                "invite_back_message": self._g("invite_back_message"),
                "max_consecutive_errors": int(self._g("max_consecutive_errors", "5")),
                "huiguan_message_round": int(self._g("huiguan_message_round", "3")),
                "direct_group_mode": self._dm(),
                "reply_interval": {
                    "min": float(self._g("reply_min", "1")),
                    "max": float(self._g("reply_max", "3")),
                },
                "chat_strategy": self.strategy.current.value or "message_pool",
                "message_pools": [],
                "message_pool_rotation": {"strategy": "sequential"},
                "chat_list_scan_interval": {"min": 2.0, "max": 4.0},
                "click_offset": {"x": 5, "y": 5},
                "delay": {"min": 0.3, "max": 0.8},
                "chat_ignore_names": ["收到的招呼", "互动通知", "订阅内容", "陌陌", "超级抢车位", "猜你喜欢", "谁看过我"],
            }
            for i in range(1, self._pool_cnt + 1):
                msgs = [m.strip() for m in self.pools[i].current.value.split("\n") if m.strip()]
                if msgs:
                    cfg["message_pools"].append({"id": i, "messages": msgs})

            r = requests.put(f"{API}/api/config", json={"config": cfg}, timeout=10)
            d = r.json()
            self._st("保存成功" if d.get("ok") else d.get("error", "失败"), SUCCESS if d.get("ok") else DANGER)
        except Exception as ex:
            self._st(str(ex), DANGER)

    def _g(self, k, d=""):
        try:
            return self.fields[k].current.value or d
        except Exception:
            return d

    def _dm(self):
        try:
            return self.direct_mode_switch.current.value
        except Exception:
            return False

    def _st(self, msg, color):
        try:
            self.status.current.value = msg
            self.status.current.color = color
            self.status.current.update()
        except Exception:
            pass

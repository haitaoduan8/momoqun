"""账号检测面板 — Neon Aurora 风格，聚光灯效果 + 青色光效。"""

from __future__ import annotations

import threading
import time
from datetime import datetime

import flet as ft
import requests

from ui.theme import (
    BG, BG_CARD, BG_ELEVATED, BG_SURFACE, BORDER, BORDER_GLOW, DIVIDER,
    TEXT, TEXT_SECONDARY, TEXT_MUTED, TEXT_ACCENT,
    ACCENT, ACCENT_DIM, ACCENT_GLOW, SUCCESS, SUCCESS_DIM, WARNING, WARNING_DIM, DANGER, DANGER_DIM,
    CARD_RADIUS, ICON_RADIUS,
    accent_btn, outline_btn, section_title, badge, icon_badge, separator,
)

API = "http://localhost:5100"

_PRESETS = [15, 30, 60, 120]


def _fmt_time(ts: float) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    except Exception:
        return "—"


def _status_badge(status: str):
    if status == "abnormal":
        return badge("账号异常", DANGER)
    if status == "ok":
        return badge("正常", SUCCESS)
    if status == "unknown":
        return badge("未知", WARNING)
    if status == "error":
        return badge("检测失败", DANGER)
    return badge("未检测", TEXT_MUTED)


class AccountCheckPanel:
    def __init__(self, page: ft.Page) -> None:
        self.page = page

        self.enable_switch = ft.Ref[ft.Switch]()
        self.interval_dropdown = ft.Ref[ft.Dropdown]()
        self.custom_input = ft.Ref[ft.TextField]()
        self.list_col = ft.Ref[ft.Column]()
        self.abnormal_count = ft.Ref[ft.Text]()
        self.status_hint = ft.Ref[ft.Text]()

        self._running = False
        self._suppress_change = False

    def build(self) -> ft.Container:
        header = ft.Container(
            content=ft.Row([
                section_title("账号检测", ft.Icons.SHIELD_OUTLINED),
                ft.Container(
                    content=ft.Text(ref=self.abnormal_count, value="0", size=13,
                                    color=DANGER, weight="w700"),
                    bgcolor=DANGER_DIM,
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=14, vertical=6),
                    border=ft.border.all(1, f"{DANGER}40"),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=12,
                        color=DANGER_DIM,
                    ),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(horizontal=28, vertical=24),
            border=ft.border.only(bottom=ft.BorderSide(1, DIVIDER)),
        )

        switch = ft.Switch(
            ref=self.enable_switch,
            value=False,
            active_color=ACCENT,
            on_change=self._on_toggle_enable,
            scale=0.85,
        )

        dropdown = ft.Dropdown(
            ref=self.interval_dropdown,
            value="30",
            options=[ft.dropdown.Option(str(m), f"{m} 分钟") for m in _PRESETS]
                    + [ft.dropdown.Option("custom", "自定义…")],
            on_change=self._on_interval_change,
            dense=True,
            border_color=BORDER,
            focused_border_color=ACCENT,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
            width=160,
        )

        custom_field = ft.TextField(
            ref=self.custom_input,
            value="",
            hint_text="自定义分钟",
            visible=False,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self._on_custom_submit,
            border_color=BORDER,
            focused_border_color=ACCENT,
            text_size=13,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
            width=130,
        )

        controls = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("启用自动检测", size=15, color=TEXT, weight="w600"),
                    ft.Container(expand=True),
                    switch,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=10),
                ft.Text("检测周期", size=12, color=TEXT_MUTED, weight="w600"),
                ft.Row([
                    dropdown,
                    custom_field,
                ], spacing=12),
                ft.Container(height=14),
                accent_btn("立即检测一次", self._on_trigger_now, icon=ft.Icons.PLAY_CIRCLE_OUTLINED),
                ft.Container(
                    content=ft.Text(ref=self.status_hint, value="", size=11, color=TEXT_MUTED, weight="w500"),
                    padding=ft.padding.only(top=8),
                ),
            ], spacing=10),
            padding=ft.padding.symmetric(horizontal=28, vertical=22),
            border=ft.border.only(bottom=ft.BorderSide(1, DIVIDER)),
        )

        list_header = ft.Container(
            content=ft.Text("异常账号", size=13, color=TEXT_MUTED, weight="w700"),
            padding=ft.padding.only(left=28, right=28, top=22, bottom=8),
        )

        list_area = ft.Container(
            content=ft.Column(
                ref=self.list_col,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
            padding=ft.padding.symmetric(horizontal=24, vertical=8),
        )

        panel = ft.Container(
            content=ft.Column(
                [header, controls, list_header, list_area],
                spacing=0,
                expand=True,
            ),
            width=360,
            bgcolor=BG_SURFACE,
            border=ft.border.only(left=ft.BorderSide(1, BORDER)),
        )
        return panel

    def did_mount(self) -> None:
        self._running = True
        threading.Thread(target=self._poll, daemon=True).start()

    def will_unmount(self) -> None:
        self._running = False

    def _poll(self) -> None:
        while self._running:
            self._fetch_and_render()
            time.sleep(3)

    def _fetch_and_render(self) -> None:
        try:
            r = requests.get(f"{API}/api/account-check/status", timeout=5)
            if not r.ok:
                return
            data = r.json() or {}
            self._render(data)
        except Exception:
            pass

    def _render(self, data: dict) -> None:
        cfg = (data or {}).get("config") or {}
        devices = (data or {}).get("devices") or []

        self._suppress_change = True
        try:
            sw = self.enable_switch.current
            if sw:
                sw.value = bool(cfg.get("enabled", False))
                sw.update()

            interval = int(cfg.get("interval_minutes", 30) or 30)
            dd = self.interval_dropdown.current
            ci = self.custom_input.current
            if dd:
                if interval in _PRESETS:
                    dd.value = str(interval)
                    if ci:
                        ci.visible = False
                        ci.update()
                else:
                    dd.value = "custom"
                    if ci:
                        ci.value = str(interval)
                        ci.visible = True
                        ci.update()
                dd.update()
        except Exception:
            pass
        finally:
            self._suppress_change = False

        problem_devs = [d for d in devices if d.get("account_status") in ("abnormal", "unknown", "error")]
        try:
            self.abnormal_count.current.value = str(len(problem_devs))
            self.abnormal_count.current.update()
        except Exception:
            pass

        if not problem_devs:
            cards = [self._empty_state()]
        else:
            cards = [self._abnormal_card(d) for d in problem_devs]

        try:
            self.list_col.current.controls = cards
            self.list_col.current.update()
        except Exception:
            pass

    def _empty_state(self) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(ft.Icons.VERIFIED_OUTLINED, size=44, color=TEXT_MUTED),
                    bgcolor=ACCENT_DIM,
                    border_radius=24,
                    padding=20,
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=20,
                        color=ACCENT_GLOW,
                    ),
                ),
                ft.Text("暂无异常账号", size=14, color=TEXT_MUTED, weight="w600",
                        text_align="center"),
                ft.Text("启用自动检测或点击立即检测", size=12,
                        color=TEXT_MUTED, text_align="center", weight="w500"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            padding=ft.padding.all(44),
            alignment=ft.alignment.center,
        )

    def _abnormal_card(self, d: dict) -> ft.Container:
        ser = d.get("serial", "?")
        status = d.get("account_status", "unknown")
        last_at = float(d.get("last_check_at") or 0.0)

        accent_color = DANGER if status == "abnormal" else WARNING

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=22, color=accent_color),
                        bgcolor=f"{accent_color}15",
                        border_radius=ICON_RADIUS,
                        padding=10,
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=15,
                            color=f"{accent_color}30",
                        ),
                    ),
                    ft.Text(ser, size=14, weight="w700", color=TEXT,
                            font_family="monospace",
                            expand=True,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    _status_badge(status),
                ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.Container(
                        content=ft.Text(f"上次检测 {_fmt_time(last_at)}",
                                        size=11, color=TEXT_MUTED, weight="w500"),
                        padding=ft.padding.only(left=44),
                    ),
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        text="已处理",
                        on_click=lambda e, s=ser: self._dismiss(s),
                        bgcolor=ACCENT_DIM,
                        color=ACCENT,
                        height=32,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.padding.symmetric(horizontal=16),
                            text_style=ft.TextStyle(size=11, weight="w700"),
                            side=ft.BorderSide(1, f"{ACCENT}40"),
                            shadow_color=ACCENT_GLOW,
                            elevation=4,
                        ),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=10),
            bgcolor=BG_CARD,
            border_radius=CARD_RADIUS,
            padding=ft.padding.all(18),
            border=ft.border.all(1, f"{accent_color}30"),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                offset=ft.Offset(0, 6),
            ),
        )

    def _on_toggle_enable(self, e) -> None:
        if self._suppress_change:
            return
        enabled = bool(self.enable_switch.current.value)
        self._post_config({"enabled": enabled})

    def _on_interval_change(self, e) -> None:
        if self._suppress_change:
            return
        v = self.interval_dropdown.current.value
        ci = self.custom_input.current
        if v == "custom":
            if ci:
                ci.visible = True
                ci.update()
            return
        if ci:
            ci.visible = False
            ci.update()
        try:
            minutes = int(v)
            self._post_config({"interval_minutes": minutes})
        except Exception:
            pass

    def _on_custom_submit(self, e) -> None:
        if self._suppress_change:
            return
        try:
            minutes = int(self.custom_input.current.value)
            if minutes < 1:
                self._show_hint("最小 1 分钟")
                return
            self._post_config({"interval_minutes": minutes})
        except Exception:
            self._show_hint("请输入有效数字")

    def _on_trigger_now(self, e) -> None:
        def _do() -> None:
            try:
                r = requests.post(f"{API}/api/account-check/trigger", json={}, timeout=10)
                if r.ok:
                    n = (r.json() or {}).get("triggered", 0)
                    self._show_hint(f"已触发 {n} 台设备，等本轮结束后开始检测")
                else:
                    self._show_hint("触发失败")
            except Exception:
                self._show_hint("触发失败")
            self._fetch_and_render()
        threading.Thread(target=_do, daemon=True).start()

    def _dismiss(self, serial: str) -> None:
        def _do() -> None:
            try:
                requests.post(f"{API}/api/account-check/dismiss",
                              json={"serial": serial}, timeout=10)
            except Exception:
                pass
            self._fetch_and_render()
        threading.Thread(target=_do, daemon=True).start()

    def _post_config(self, body: dict) -> None:
        def _do() -> None:
            try:
                r = requests.post(f"{API}/api/account-check/config", json=body, timeout=10)
                if r.ok:
                    cfg = (r.json() or {}).get("config") or {}
                    if "enabled" in body:
                        self._show_hint("已启用自动检测" if cfg.get("enabled") else "已停用自动检测")
                    elif "interval_minutes" in body:
                        self._show_hint(f"周期已设为 {cfg.get('interval_minutes')} 分钟")
            except Exception:
                self._show_hint("保存配置失败")
            self._fetch_and_render()
        threading.Thread(target=_do, daemon=True).start()

    def _show_hint(self, text: str) -> None:
        try:
            self.status_hint.current.value = text
            self.status_hint.current.update()
        except Exception:
            pass

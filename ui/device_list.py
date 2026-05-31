"""设备卡片列表 — Neon Aurora 风格，聚光灯卡片 + 青色状态指示。"""

import flet as ft
import threading
import time
import requests
from ui.theme import (
    BG, BG_CARD, BG_HOVER, BORDER, BORDER_GLOW, DIVIDER,
    TEXT, TEXT_SECONDARY, TEXT_MUTED, TEXT_ACCENT,
    ACCENT, ACCENT_DIM, ACCENT_GLOW, SUCCESS, SUCCESS_DIM, WARNING, WARNING_DIM, DANGER, DANGER_DIM,
    CARD_RADIUS, ICON_RADIUS,
    state_color, state_label, state_icon,
    badge, icon_badge, separator,
)

API = "http://localhost:5100"


def _small_btn(text, on_click, color, bg_dim):
    """紧凑操作按钮 - 发光效果。"""
    return ft.ElevatedButton(
        text=text,
        on_click=on_click,
        bgcolor=bg_dim,
        color=color,
        height=32,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.padding.symmetric(horizontal=16),
            text_style=ft.TextStyle(size=11, weight="w700"),
            side=ft.BorderSide(1, f"{color}30"),
            shadow_color=f"{color}25",
            elevation=4,
        ),
    )


def _device_card(d, on_start, on_pause, on_resume, on_remove):
    """单个设备卡片 - 聚光灯发光边框。"""
    ser = d.get("serial", "?")
    name = d.get("name", ser)
    st = d.get("state", "stopped")
    sc = state_color(st)
    sl = state_label(st)
    si = state_icon(st)

    # 内联统计标签
    stats_parts = []
    for key, label in [("round_number", "轮"), ("friends_total", "友"), ("friends_this_round", "本")]:
        v = d.get(key)
        if v and str(v) != "0":
            stats_parts.append(f"{label}:{v}")
    stats_text = " ".join(stats_parts)

    return ft.Container(
        content=ft.Column([
            # 第一行：名称 + 统计 + 状态徽章
            ft.Row([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(si, size=20, color=sc),
                        bgcolor=f"{sc}15",
                        border_radius=ICON_RADIUS,
                        padding=10,
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=15,
                            color=f"{sc}30",
                        ),
                    ),
                    ft.Text(name, size=16, weight="w700", color=TEXT),
                ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(stats_text, size=11, color=TEXT_MUTED, weight="w500") if stats_text else ft.Container(),
                ft.Container(expand=True),
                badge(sl, sc),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

            # 第二行：端口号 + 操作按钮
            ft.Row([
                ft.Container(
                    content=ft.Text(ser, size=11, color=TEXT_MUTED, font_family="monospace", weight="w500"),
                    bgcolor=ACCENT_DIM,
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                ),
                ft.Container(width=14),
                _small_btn("开始", lambda e, s=ser: on_start(s), SUCCESS, SUCCESS_DIM),
                _small_btn("暂停", lambda e, s=ser: on_pause(s), WARNING, WARNING_DIM),
                _small_btn("继续", lambda e, s=ser: on_resume(s), ACCENT, ACCENT_DIM),
                ft.Container(expand=True),
                _small_btn("删除", lambda e, s=ser: on_remove(s), DANGER, DANGER_DIM),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=14),
        bgcolor=BG_CARD,
        border_radius=CARD_RADIUS,
        padding=ft.padding.symmetric(horizontal=24, vertical=18),
        border=ft.border.all(1, BORDER),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=25,
            color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
            offset=ft.Offset(0, 6),
        ),
    )


def _empty_state():
    """无设备时的空状态 - 聚光灯效果。"""
    return ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Container(
                    content=ft.Icon(ft.Icons.PHONE_ANDROID, size=52, color=TEXT_MUTED),
                    bgcolor=ACCENT_DIM,
                    border_radius=28,
                    padding=24,
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=30,
                        color=ACCENT_GLOW,
                    ),
                ),
                padding=ft.padding.only(bottom=20),
            ),
            ft.Text("暂无设备", size=20, weight="w700", color=TEXT_MUTED, text_align="center"),
            ft.Text("在左侧 ADB 面板连接并添加设备", size=13, color=TEXT_MUTED, text_align="center", weight="w500"),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        padding=ft.padding.all(100),
        alignment=ft.alignment.center,
    )


class DeviceList:
    def __init__(self, page: ft.Page):
        self.page = page
        self.list = ft.Ref[ft.Column]()
        self.count = ft.Ref[ft.Text]()
        self.running = False

    def build(self):
        return ft.Container(
            content=ft.Column([
                ft.Column(ref=self.list, spacing=14),
            ], spacing=18, scroll=ft.ScrollMode.AUTO),
        )

    def did_mount(self):
        self.running = True
        threading.Thread(target=self._poll, daemon=True).start()

    def will_unmount(self):
        self.running = False

    def refresh(self):
        threading.Thread(target=self._fetch_and_render, daemon=True).start()

    def _poll(self):
        while self.running:
            self._fetch_and_render()
            time.sleep(3)

    def _fetch_and_render(self):
        try:
            r = requests.get(f"{API}/api/devices", timeout=5)
            if r.ok and isinstance(r.json(), list):
                self._render(r.json())
        except Exception:
            pass

    def _render(self, devs):
        if not devs:
            cards = [_empty_state()]
        else:
            cards = [
                _device_card(
                    d,
                    lambda s: self._act("start", s),
                    lambda s: self._act("pause", s),
                    lambda s: self._act("resume", s),
                    lambda s: self._act("remove", s),
                )
                for d in devs
            ]

        try:
            self.count.current.value = f"({len(devs)})"
            self.count.current.update()
            self.list.current.controls = cards
            self.list.current.update()
        except Exception:
            pass

    def _act(self, action, ser):
        def _do():
            try:
                requests.post(f"{API}/api/devices/{action}", json={"serial": ser}, timeout=10)
            except Exception:
                pass
            self._fetch_and_render()
        threading.Thread(target=_do, daemon=True).start()

    def _init_dev(self, ser):
        threading.Thread(target=lambda: requests.post(
            f"{API}/api/adb/init", json={"serial": ser}, timeout=140
        ), daemon=True).start()

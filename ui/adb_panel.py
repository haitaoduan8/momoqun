"""ADB 管理面板 — Neon Aurora 风格，聚光灯效果 + 青色光效。"""

import flet as ft
import threading
import requests
from ui.theme import (
    BG_CARD, BG_INPUT, BG_HOVER, BORDER, BORDER_FOCUS, BORDER_GLOW, DIVIDER,
    TEXT, TEXT_SECONDARY, TEXT_MUTED, TEXT_ACCENT,
    ACCENT, ACCENT_DIM, ACCENT_GLOW, SUCCESS, SUCCESS_DIM, DANGER, DANGER_DIM,
    BTN_RADIUS, CARD_RADIUS, INPUT_RADIUS, ICON_RADIUS,
    accent_btn, outline_btn, form_input, section_title, icon_badge, separator,
)

API = "http://localhost:5100"


def _device_row(serial, on_init, on_add, on_disc):
    """单个扫描到的设备行 - 青色发光边框。"""
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.PHONE_ANDROID, size=18, color=ACCENT),
                bgcolor=ACCENT_DIM,
                border_radius=ICON_RADIUS,
                padding=10,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=12,
                    color=ACCENT_GLOW,
                ),
            ),
            ft.Text(serial, size=12, color=TEXT, expand=True, font_family="monospace",
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Row([
                ft.TextButton(
                    "初始化",
                    on_click=lambda e, s=serial: on_init(s),
                    style=ft.ButtonStyle(
                        color=ACCENT,
                        text_style=ft.TextStyle(size=11, weight="w600"),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ),
                ft.TextButton(
                    "添加",
                    on_click=lambda e, s=serial: on_add(s),
                    style=ft.ButtonStyle(
                        color=SUCCESS,
                        text_style=ft.TextStyle(size=11, weight="w600"),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ),
                ft.TextButton(
                    "断开",
                    on_click=lambda e, s=serial: on_disc(s),
                    style=ft.ButtonStyle(
                        color=DANGER,
                        text_style=ft.TextStyle(size=11, weight="w600"),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ),
            ], spacing=0),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=BG_CARD,
        border_radius=CARD_RADIUS,
        padding=ft.padding.symmetric(horizontal=18, vertical=14),
        border=ft.border.all(1, BORDER),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=15,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
    )


class ADBPanel:
    def __init__(self, device_list=None):
        self.status = ft.Ref[ft.Text]()
        self.addr = ft.Ref[ft.TextField]()
        self.dev_list = ft.Ref[ft.Column]()
        self._device_list = device_list

    def build(self):
        return ft.Container(
            content=ft.Column([
                # 标题区
                section_title("ADB 设备管理", ft.Icons.PHONE_ANDROID),

                # 连接输入行
                ft.Container(
                    content=ft.Row([
                        form_input(self.addr, hint="127.0.0.1:7555", height=44),
                        accent_btn("连接", self._connect, icon=ft.Icons.LINK, height=44),
                    ], spacing=12),
                    padding=ft.padding.only(top=18),
                ),

                # 扫描按钮 + 状态
                ft.Container(
                    content=ft.Row([
                        outline_btn("扫描设备", self._scan, height=38),
                        ft.Container(expand=True),
                        ft.Text(ref=self.status, size=11, color=TEXT_MUTED, weight="w500"),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.only(top=10),
                ),

                # 分割线
                separator(),

                # 设备列表
                ft.Column(ref=self.dev_list, spacing=10),
            ], spacing=0),
            bgcolor=BG_CARD,
            border_radius=CARD_RADIUS,
            padding=ft.padding.symmetric(horizontal=28, vertical=24),
            border=ft.border.all(1, BORDER),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=25,
                color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                offset=ft.Offset(0, 6),
            ),
        )

    # ─── API ───

    def _connect(self, e):
        a = self.addr.current.value.strip()
        if not a:
            self._status("请输入地址", DANGER)
            return
        self._status("连接中...", TEXT_SECONDARY)
        threading.Thread(target=self._conn, args=(a,), daemon=True).start()

    def _conn(self, addr):
        try:
            r = requests.post(f"{API}/api/adb/connect", json={"address": addr}, timeout=20)
            d = r.json()
            self._status(f"已连接 {addr}" if d.get("ok") else d.get("error", "失败"), SUCCESS if d.get("ok") else DANGER)
            self._scan(None)
        except Exception as ex:
            self._status(str(ex), DANGER)

    def _scan(self, e):
        self._status("扫描中...", TEXT_SECONDARY)
        threading.Thread(target=self._sc, daemon=True).start()

    def _sc(self):
        try:
            r = requests.get(f"{API}/api/adb/devices", timeout=10)
            devs = r.json().get("devices", [])

            added_serials: set = set()
            try:
                r2 = requests.get(f"{API}/api/devices", timeout=5)
                if r2.ok:
                    body = r2.json()
                    if isinstance(body, list):
                        added_serials = {
                            (x.get("serial") or "") for x in body if isinstance(x, dict)
                        }
            except Exception:
                pass

            pending = [d for d in devs if (d.get("serial") or "") not in added_serials]

            items = []
            for d in pending:
                s = d.get("serial", "")
                items.append(_device_row(s, self._init, self._add, self._disc))
            if not items:
                if devs:
                    hint = ft.Text(
                        f"扫描到 {len(devs)} 台设备，均已添加到右侧",
                        size=12, color=TEXT_MUTED, weight="w500",
                    )
                else:
                    hint = ft.Text("未发现设备", size=12, color=TEXT_MUTED, weight="w500")
                items = [
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Icon(ft.Icons.DEVICE_UNKNOWN, size=22, color=TEXT_MUTED),
                                bgcolor=ACCENT_DIM,
                                border_radius=ICON_RADIUS,
                                padding=10,
                            ),
                            hint,
                        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.symmetric(vertical=14),
                    )
                ]
            self.dev_list.current.controls = items
            self.dev_list.current.update()
            self._status("扫描完成", TEXT_MUTED)
        except Exception as ex:
            self._status(str(ex), DANGER)

    def _init(self, ser):
        self._status(f"初始化 {ser}...", TEXT_SECONDARY)
        threading.Thread(target=self._in, args=(ser,), daemon=True).start()

    def _in(self, ser):
        try:
            r = requests.post(f"{API}/api/adb/init", json={"serial": ser}, timeout=140)
            d = r.json()
            self._status(f"{ser} 完成" if d.get("ok") else d.get("error", "失败"), SUCCESS if d.get("ok") else DANGER)
        except Exception as ex:
            self._status(str(ex), DANGER)

    def _add(self, ser):
        self._status(f"添加 {ser}...", TEXT_SECONDARY)
        threading.Thread(target=self._ad, args=(ser,), daemon=True).start()

    def _ad(self, ser):
        try:
            r = requests.post(f"{API}/api/devices/add", json={"serial": ser, "name": ser}, timeout=10)
            d = r.json()
            self._status(f"{ser} 已添加" if d.get("ok") else d.get("error", "失败"), SUCCESS if d.get("ok") else DANGER)
            if d.get("ok"):
                if self._device_list:
                    self._device_list.refresh()
                self._sc()
        except Exception as ex:
            self._status(str(ex), DANGER)

    def _disc(self, ser):
        self._status(f"断开 {ser}...", TEXT_SECONDARY)
        threading.Thread(target=self._dc, args=(ser,), daemon=True).start()

    def _dc(self, ser):
        try:
            r = requests.post(f"{API}/api/adb/disconnect", json={"address": ser}, timeout=10)
            d = r.json()
            self._status(f"{ser} 已断开" if d.get("ok") else "失败", SUCCESS if d.get("ok") else DANGER)
            self._scan(None)
        except Exception as ex:
            self._status(str(ex), DANGER)

    def _status(self, msg, color):
        try:
            self.status.current.value = msg
            self.status.current.color = color
            self.status.current.update()
        except Exception:
            pass

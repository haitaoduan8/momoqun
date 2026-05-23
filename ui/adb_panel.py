"""ADB 管理面板 — Card 包裹 + 圆角按钮。"""

import flet as ft
import threading
import requests
from ui.theme import (
    BG_CARD, BORDER, TEXT, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, DANGER, BTN_RADIUS,
)

API = "http://localhost:5100"


def _btn(text, on_click, color=ACCENT, height=36):
    return ft.ElevatedButton(
        text=text,
        on_click=on_click,
        bgcolor=color,
        color="#ffffff",
        height=height,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=16),
        ),
    )


def _outline_btn(text, on_click, height=34):
    return ft.OutlinedButton(
        text=text,
        on_click=on_click,
        height=height,
        style=ft.ButtonStyle(
            color=TEXT_SECONDARY,
            side=ft.BorderSide(1, BORDER),
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=14),
        ),
    )


class ADBPanel:
    def __init__(self):
        self.status = ft.Ref[ft.Text]()
        self.addr = ft.Ref[ft.TextField]()
        self.dev_list = ft.Ref[ft.Column]()

    def build(self):
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("ADB 管理", size=15, weight="bold", color=TEXT),
                    ft.Divider(height=1, color=BORDER),
                    ft.Row([
                        ft.TextField(
                            ref=self.addr,
                            hint_text="127.0.0.1:7555",
                            border_color=BORDER,
                            bgcolor=BG_CARD,
                            color=TEXT,
                            text_size=14,
                            expand=True,
                            height=40,
                            content_padding=ft.Padding(left=12, top=0, right=12, bottom=0),
                        ),
                        _btn("连接", self._connect),
                    ], spacing=8),
                    ft.Row([
                        _outline_btn("扫描设备", self._scan),
                        ft.Text(ref=self.status, size=13, color=TEXT_SECONDARY),
                    ], spacing=8),
                    ft.Divider(height=1, color=BORDER),
                    ft.Column(ref=self.dev_list, spacing=6),
                ], spacing=10),
                padding=20,
            ),
            color=BG_CARD,
            elevation=0,
            margin=10,
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
            items = []
            for d in devs:
                s = d.get("serial", "")
                items.append(ft.Row([
                    ft.Text(s, size=13, color=TEXT, expand=True),
                    ft.TextButton("初始化", on_click=lambda e, ser=s: self._init(ser),
                                  style=ft.ButtonStyle(color=ACCENT)),
                    ft.TextButton("添加", on_click=lambda e, ser=s: self._add(ser),
                                  style=ft.ButtonStyle(color=SUCCESS)),
                    ft.TextButton("断开", on_click=lambda e, ser=s: self._disc(ser),
                                  style=ft.ButtonStyle(color=DANGER)),
                ], spacing=6))
            if not items:
                items = [ft.Text("无设备", size=13, color=TEXT_MUTED)]
            self.dev_list.current.controls = items
            self.dev_list.current.update()
            self._status("扫描完成", TEXT_SECONDARY)
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

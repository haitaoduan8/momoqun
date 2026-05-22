"""ADB 管理面板：连接模拟器 + 扫描设备 + 初始化/添加。"""

import flet as ft
import threading
import requests
from ui.theme import (
    BG_SECONDARY, BG_CARD, BG_HOVER, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, DANGER, SUCCESS,
)

API_BASE = "http://localhost:5100"


class ADBPanel:
    def __init__(self):
        super().__init__()
        self._status = ft.Ref[ft.Text]()
        self._addr_field = ft.Ref[ft.TextField]()
        self._device_list = ft.Ref[ft.Column]()

    def build(self):
        self._status_col = ft.Text(ref=self._status, size=12, color=TEXT_SECONDARY)

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        [ft.Text("连接模拟器", size=13, color=TEXT_PRIMARY, weight="bold")],
                    ),
                    on_click=lambda _: self._toggle(),
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row([
                                ft.TextField(
                                    ref=self._addr_field,
                                    hint_text="127.0.0.1:7555",
                                    border_color=BORDER,
                                    bgcolor=BG_CARD,
                                    color=TEXT_PRIMARY,
                                    text_size=13,
                                    expand=True,
                                    height=36,
                                    content_padding=ft.padding.only(left=10, right=10),
                                ),
                                ft.ElevatedButton(
                                    "连接", on_click=self._do_connect,
                                    bgcolor=ACCENT, color="#ffffff",
                                    height=36, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                                ),
                            ], spacing=6),
                            ft.Row([
                                ft.OutlinedButton(
                                    "扫描设备", on_click=self._do_scan,
                                    style=ft.ButtonStyle(color=TEXT_SECONDARY, side=ft.BorderSide(1, BORDER)),
                                    height=32,
                                ),
                                self._status_col,
                            ]),
                            ft.Divider(height=1, color=BORDER),
                            ft.Column(ref=self._device_list, spacing=4),
                        ],
                        spacing=8,
                    ),
                    padding=ft.padding.all(10),
                    bgcolor=BG_SECONDARY,
                    border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
                ),
            ],
        )

    def _toggle(self):
        """折叠/展开面板 — 通过更新页面。"""
        pass  # Flet ExpansionTile 可用，保持简单先不折叠

    # ─── API 调用 ───

    def _do_connect(self, e):
        addr = self._addr_field.current.value.strip()
        if not addr:
            self._set_status("请输入地址", DANGER)
            return
        self._set_status("连接中...", TEXT_SECONDARY)
        threading.Thread(target=self._connect_thread, args=(addr,), daemon=True).start()

    def _connect_thread(self, addr):
        try:
            r = requests.post(f"{API_BASE}/api/adb/connect",
                              json={"address": addr}, timeout=20)
            d = r.json()
            if d.get("ok"):
                self._set_status(f"已连接 {addr}", SUCCESS)
            else:
                self._set_status(d.get("error") or d.get("output", "连接失败"), DANGER)
            self._do_scan(None)
        except Exception as ex:
            self._set_status(f"错误: {ex}", DANGER)

    def _do_scan(self, e):
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        try:
            r = requests.get(f"{API_BASE}/api/adb/devices", timeout=10)
            data = r.json()
            devs = data.get("devices", [])
            items = []
            for dev in devs:
                serial = dev.get("serial", "")
                items.append(
                    ft.Row([
                        ft.Text(serial, size=12, color=TEXT_PRIMARY, expand=True),
                        ft.TextButton("初始化", on_click=lambda e, s=serial: self._do_init(s),
                                      style=ft.ButtonStyle(color=ACCENT), height=28),
                        ft.TextButton("添加", on_click=lambda e, s=serial: self._do_add(s),
                                      style=ft.ButtonStyle(color=SUCCESS), height=28),
                    ], spacing=4),
                )
            if not items:
                items = [ft.Text("无设备", size=12, color=TEXT_MUTED)]
            self._device_list.current.controls = items
            self._device_list.current.update()
        except Exception as ex:
            self._set_status(f"扫描失败: {ex}", DANGER)

    def _do_init(self, serial):
        self._set_status(f"初始化 {serial}...", TEXT_SECONDARY)
        threading.Thread(target=self._init_thread, args=(serial,), daemon=True).start()

    def _init_thread(self, serial):
        try:
            r = requests.post(f"{API_BASE}/api/adb/init",
                              json={"serial": serial}, timeout=130)
            d = r.json()
            if d.get("ok"):
                self._set_status(f"{serial} 初始化完成", SUCCESS)
            else:
                self._set_status(d.get("error", "初始化失败"), DANGER)
        except Exception as ex:
            self._set_status(f"错误: {ex}", DANGER)

    def _do_add(self, serial):
        self._set_status(f"添加 {serial}...", TEXT_SECONDARY)
        threading.Thread(target=self._add_thread, args=(serial,), daemon=True).start()

    def _add_thread(self, serial):
        try:
            r = requests.post(f"{API_BASE}/api/devices/add",
                              json={"serial": serial, "name": serial}, timeout=10)
            d = r.json()
            if d.get("ok"):
                self._set_status(f"{serial} 已添加", SUCCESS)
            else:
                self._set_status(d.get("error", "添加失败"), DANGER)
        except Exception as ex:
            self._set_status(f"错误: {ex}", DANGER)

    def _set_status(self, msg, color):
        try:
            self._status.current.value = msg
            self._status.current.color = color
            self._status.current.update()
            self._status_col.update()
        except Exception:
            pass

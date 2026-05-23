"""设备卡片列表 — 圆角 Card 每设备独立控制 3秒轮询。"""

import flet as ft
import threading
import time
import requests
from ui.theme import (
    BG_CARD, BG_ELEVATED, BORDER, TEXT, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, WARNING, DANGER, state_color, state_label, BTN_RADIUS,
)

API = "http://localhost:5100"


class DeviceList:
    def __init__(self, page: ft.Page):
        self.page = page
        self.list = ft.Ref[ft.Column]()
        self.count = ft.Ref[ft.Text]()
        self.running = False

    def build(self):
        return ft.Container(
            content=ft.Column([
                ft.Text(ref=self.count, size=14, color=TEXT_SECONDARY),
                ft.Column(ref=self.list, spacing=10),
            ], spacing=12),
            margin=ft.margin.only(top=0, bottom=0),
        )

    def did_mount(self):
        self.running = True
        threading.Thread(target=self._poll, daemon=True).start()

    def will_unmount(self):
        self.running = False

    def _poll(self):
        while self.running:
            try:
                r = requests.get(f"{API}/api/devices", timeout=5)
                if r.ok and isinstance(r.json(), list):
                    self._render(r.json())
            except Exception:
                pass
            time.sleep(3)

    def _render(self, devs):
        cards = []
        for d in devs:
            ser = d.get("serial", "?")
            name = d.get("name", ser)
            st = d.get("state", "stopped")
            sc = state_color(st)
            sl = state_label(st)

            parts = []
            for k in [("round_number", "轮次"), ("friends_total", "好友"), ("friends_this_round", "本轮")]:
                v = d.get(k[0])
                if v and v != "0":
                    parts.append(f"{k[1]}: {v}")
            info = "  |  ".join(parts) if parts else "暂无数据"

            cards.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(name, size=15, weight="bold", color=TEXT),
                                ft.Text(ser, size=12, color=TEXT_MUTED),
                            ], spacing=10),
                            ft.Row([
                                ft.Text(sl, size=13, color=sc),
                                ft.Text(info, size=12, color=TEXT_SECONDARY),
                            ], spacing=14),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.Icons.PLAY_ARROW, icon_color=SUCCESS,
                                    tooltip="启动",
                                    on_click=lambda e, s=ser: self._act("start", s),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.PAUSE, icon_color=WARNING,
                                    tooltip="暂停",
                                    on_click=lambda e, s=ser: self._act("pause", s),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.STOP, icon_color=DANGER,
                                    tooltip="停止",
                                    on_click=lambda e, s=ser: self._act("stop", s),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.REPLAY, icon_color=ACCENT,
                                    tooltip="继续",
                                    on_click=lambda e, s=ser: self._act("resume", s),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.BUILD, icon_color=TEXT_SECONDARY,
                                    tooltip="初始化",
                                    on_click=lambda e, s=ser: self._init_dev(s),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE, icon_color=DANGER,
                                    tooltip="移除设备",
                                    on_click=lambda e, s=ser: self._act("remove", s),
                                ),
                            ], spacing=4),
                        ], spacing=8),
                        padding=20,
                    ),
                    color=BG_CARD,
                    elevation=0,
                    margin=ft.margin.only(bottom=6),
                )
            )

        if not cards:
            cards = [
                ft.Container(
                    content=ft.Text("暂无设备，去左侧添加", size=14, color=TEXT_MUTED,
                                    text_align="center"),
                    padding=ft.padding.all(30),
                    margin=10,
                )
            ]

        try:
            self.count.current.value = f"已连接设备 ({len(devs)})"
            self.count.current.update()
            self.list.current.controls = cards
            self.list.current.update()
        except Exception:
            pass

    def _act(self, action, ser):
        threading.Thread(target=lambda: requests.post(
            f"{API}/api/devices/{action}", json={"serial": ser}, timeout=10
        ), daemon=True).start()

    def _init_dev(self, ser):
        threading.Thread(target=lambda: requests.post(
            f"{API}/api/adb/init", json={"serial": ser}, timeout=140
        ), daemon=True).start()

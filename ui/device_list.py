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


def _ctrl_btn(text, on_click, color=ACCENT, height=30):
    """设备控制按钮 — 小尺寸圆角文字按钮。"""
    return ft.ElevatedButton(
        text=text,
        on_click=on_click,
        bgcolor=color,
        color="#ffffff",
        height=height,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=10),
            text_style=ft.TextStyle(size=12),
        ),
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

    def refresh(self):
        """外部触发刷新（添加设备后立即调用）。"""
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
                                _ctrl_btn("开始", lambda e, s=ser: self._act("start", s),
                                          color=SUCCESS),
                                _ctrl_btn("暂停", lambda e, s=ser: self._act("pause", s),
                                          color=WARNING),
                                _ctrl_btn("继续", lambda e, s=ser: self._act("resume", s),
                                          color=ACCENT),
                                _ctrl_btn("删除设备", lambda e, s=ser: self._act("remove", s),
                                          color=DANGER),
                            ], spacing=6),
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

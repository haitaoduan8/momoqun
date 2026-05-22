"""中部设备卡片列表：每设备 ▶⏸⏹ 独立控制按钮，3 秒轮询。"""

import flet as ft
import threading
import time
import requests
from ui.theme import (
    BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, WARNING, DANGER, STOPPED, RUNNING, PAUSED, ERROR,
)

API_BASE = "http://localhost:5100"

STATE_COLORS = {
    "running": RUNNING,
    "paused": PAUSED,
    "error": ERROR,
    "stopped": STOPPED,
}
STATE_LABELS = {
    "running": "🟢 运行中",
    "paused": "🟡 已暂停",
    "error": "🔴 错误",
    "stopped": "⚫ 已停止",
}


class DeviceList:
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self._list = ft.Ref[ft.Column]()
        self._count = ft.Ref[ft.Text]()
        self._running = False

    def build(self):
        return ft.Column(
            controls=[
                ft.Text(ref=self._count, size=13, color=TEXT_SECONDARY),
                ft.Column(ref=self._list, spacing=6),
            ],
            spacing=8,
        )

    def did_mount(self):
        self._running = True
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def will_unmount(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                r = requests.get(f"{API_BASE}/api/devices", timeout=5)
                devs = r.json() if r.ok else []
                if isinstance(devs, list):
                    self._update_ui(devs)
            except Exception:
                pass
            time.sleep(3)

    def _update_ui(self, devs):
        cards = []
        for d in devs:
            serial = d.get("serial", "?")
            name = d.get("name", serial)
            state = d.get("state", "stopped")
            sc = STATE_COLORS.get(state, STOPPED)
            label = STATE_LABELS.get(state, state)

            info_parts = []
            rn = d.get("round_number")
            if rn and rn != "0":
                info_parts.append(f"轮次: {rn}")
            ft_count = d.get("friends_total")
            if ft_count and ft_count != "0":
                info_parts.append(f"好友: {ft_count}")
            fr = d.get("friends_this_round")
            if fr and fr != "0":
                info_parts.append(f"本轮: {fr}")
            info = "  |  ".join(info_parts) if info_parts else "暂无数据"

            cards.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(name, size=13, color=TEXT_PRIMARY, weight="bold"),
                            ft.Text(serial, size=11, color=TEXT_MUTED),
                        ], spacing=8),
                        ft.Row([
                            ft.Text(label, size=12, color=sc),
                            ft.Text(info, size=11, color=TEXT_SECONDARY),
                        ], spacing=12),
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.PLAY_ARROW, icon_color=SUCCESS,
                                tooltip="启动",
                                on_click=lambda e, s=serial: self._action("start", s),
                            ),
                            ft.IconButton(
                                icon=ft.icons.PAUSE, icon_color=WARNING,
                                tooltip="暂停",
                                on_click=lambda e, s=serial: self._action("pause", s),
                            ),
                            ft.IconButton(
                                icon=ft.icons.STOP, icon_color=DANGER,
                                tooltip="停止",
                                on_click=lambda e, s=serial: self._action("stop", s),
                            ),
                            ft.IconButton(
                                icon=ft.icons.REPLAY, icon_color=ACCENT,
                                tooltip="继续",
                                on_click=lambda e, s=serial: self._action("resume", s),
                            ),
                        ], spacing=2),
                    ], spacing=6),
                    padding=ft.padding.all(12),
                    bgcolor=BG_CARD,
                    border=ft.border.all(1, BORDER),
                    border_radius=6,
                    margin=ft.margin.only(bottom=4),
                )
            )

        if not cards:
            cards = [
                ft.Container(
                    content=ft.Text("暂无设备，去左侧添加", size=13, color=TEXT_MUTED,
                                    text_align="center"),
                    padding=ft.padding.all(20),
                )
            ]

        try:
            self._count.current.value = f"已连接设备 ({len(devs)})"
            self._count.current.update()
            self._list.current.controls = cards
            self._list.current.update()
        except Exception:
            pass

    def _action(self, action, serial):
        threading.Thread(target=self._action_thread, args=(action, serial), daemon=True).start()

    def _action_thread(self, action, serial):
        try:
            requests.post(f"{API_BASE}/api/devices/{action}",
                          json={"serial": serial}, timeout=10)
        except Exception:
            pass

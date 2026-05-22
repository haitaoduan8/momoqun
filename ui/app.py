"""momoqun 桌面主窗口 — 三栏 Card 布局 + 深灰主题。"""

import flet as ft
import requests
import subprocess
import sys
import os
import atexit

from ui.theme import (
    apply_theme, BG, BG_SURFACE, BORDER, TEXT, TEXT_MUTED, BG_CARD,
)
from ui.adb_panel import ADBPanel
from ui.config_panel import ConfigPanel
from ui.device_list import DeviceList

API = "http://localhost:5100"
_FLAGS = 0x08000000 if sys.platform == "win32" else 0


def _find_adb():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        p = os.path.join(base, "adb.exe")
        if os.path.isfile(p):
            return p
        p = os.path.join(sys._MEIPASS, "adb.exe")
        if os.path.isfile(p):
            return p
    import shutil
    return shutil.which("adb") or "adb"


def _cleanup():
    try:
        requests.post(f"{API}/api/shutdown", timeout=5)
    except Exception:
        pass
    try:
        a = _find_adb()
        if a:
            subprocess.run([a, "kill-server"], timeout=10,
                           creationflags=_FLAGS,
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    except Exception:
        pass


atexit.register(_cleanup)


# ─── 主入口 ───

def main(page: ft.Page):
    page.title = "momoqun"
    page.window_width = 1250
    page.window_height = 820
    page.window_min_width = 960
    page.window_min_height = 620
    apply_theme(page)

    page.on_window_destroy = lambda _: _cleanup()

    adb = ADBPanel()
    cfg = ConfigPanel()
    dev = DeviceList(page)

    cfg.load()

    # ── 左侧 ──
    left = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("momoqun", size=20, weight="bold", color=TEXT),
                padding=ft.padding.only(left=20, top=16, bottom=10),
            ),
            adb.build(),
            cfg.build(),
        ], scroll=ft.ScrollMode.AUTO, spacing=0),
        width=290,
        bgcolor=BG_SURFACE,
        border=ft.border.only(right=ft.BorderSide(1, BORDER)),
    )

    # ── 中部 ──
    middle = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("设备列表", size=18, weight="bold", color=TEXT),
                padding=ft.padding.only(left=10, top=15, bottom=6),
            ),
            dev.build(),
        ], scroll=ft.ScrollMode.AUTO),
        expand=True,
    )

    # ── 右侧（空白） ──
    right = ft.Container(
        content=ft.Column(),
        width=200,
        bgcolor=BG_SURFACE,
        border=ft.border.only(left=ft.BorderSide(1, BORDER)),
    )

    page.add(
        ft.Row(
            controls=[left, middle, right],
            spacing=0,
            expand=True,
        )
    )

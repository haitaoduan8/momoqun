"""momoqun 桌面主窗口 — 响应式布局：Column(expand) → Row(控件+设备) + 日志(expand)。"""

import flet as ft
import requests
import subprocess
import sys
import os
import atexit

from ui.theme import apply_theme, BG, BG_CARD, BG_SURFACE, BORDER, TEXT, TEXT_SECONDARY
from ui.adb_panel import ADBPanel
from ui.config_panel import ConfigPanel
from ui.device_list import DeviceList
from ui.log_area import LogArea

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


def main(page: ft.Page):
    page.title = "momoqun"
    page.window_resizable = True
    page.window_width = 1250
    page.window_height = 820
    page.window_min_width = 960
    page.window_min_height = 620
    page.padding = 20
    apply_theme(page)

    page.on_window_destroy = lambda _: _cleanup()

    # ── 组件 ──
    adb = ADBPanel()
    cfg = ConfigPanel()
    dev = DeviceList(page)
    log = LogArea()

    cfg.load()

    # ── 标题 + 退出按钮 ──
    title = ft.Container(
        content=ft.Row([
            ft.Text("momoqun", size=22, weight="bold", color=TEXT),
            ft.ElevatedButton(
                "安全退出", on_click=lambda _: (_cleanup(), page.update()),
                bgcolor="#f87171", color="#ffffff", height=34,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.padding.symmetric(horizontal=14),
                ),
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding(left=0, top=0, right=0, bottom=10),
    )

    # ── 控件区（左 290 固定 + 右弹性） ──
    controls_row = ft.Row(
        controls=[
            ft.Container(
                content=ft.Column([
                    adb.build(),
                    cfg.build(),
                ], scroll=ft.ScrollMode.AUTO, spacing=0),
                width=300,
            ),
            ft.VerticalDivider(width=1, color=BORDER),
            ft.Container(
                content=ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("已添加设备", size=15, weight="bold", color=TEXT),
                            ft.Divider(height=1, color=BORDER),
                            dev.build(),
                        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10),
                        padding=20,
                        expand=True,
                    ),
                    color=BG_CARD,
                    elevation=0,
                    margin=10,
                    expand=True,
                ),
                width=750,
            ),
        ],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ── 日志区（默认折叠，点击展开） ──
    log_area = ft.Container(
        content=log.build(),
    )

    # ── 顶级容器 ──
    page.add(
        ft.Column(
            controls=[title, controls_row, log_area],
            expand=True,
            spacing=0,
        )
    )

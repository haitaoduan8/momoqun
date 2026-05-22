"""momoqun 桌面应用主入口 — Flet 深色三栏布局 + 退出清理。"""

import flet as ft
import requests
import subprocess
import sys
import os

from ui.theme import apply_theme, BG_PRIMARY, BG_SECONDARY, BORDER, TEXT_PRIMARY
from ui.adb_panel import ADBPanel
from ui.config_panel import ConfigPanel
from ui.device_list import DeviceList

API_BASE = "http://localhost:5100"

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0


def main(page: ft.Page):
    page.title = "momoqun"
    page.window_width = 1200
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 600
    apply_theme(page)

    # ── 退出清理 ──
    def on_window_destroy(e):
        _cleanup_on_exit()

    page.on_window_destroy = on_window_destroy

    # ── 组件 ──
    adb_panel = ADBPanel()
    config_panel = ConfigPanel()
    device_list = DeviceList(page)

    # 初始加载配置
    config_panel.load()

    # ── 布局：左(280) | 中(弹性) | 右(200空) ──
    left_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Text("momoqun", size=18, color=TEXT_PRIMARY, weight="bold"),
                    padding=ft.padding.only(left=14, top=14, bottom=10),
                ),
                adb_panel,
                ft.Divider(height=1, color=BORDER),
                config_panel,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        ),
        width=280,
        bgcolor=BG_SECONDARY,
        border=ft.border.only(right=ft.BorderSide(1, BORDER)),
    )

    middle_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Text("设备列表", size=15, color=TEXT_PRIMARY, weight="bold"),
                    padding=ft.padding.only(left=14, top=14, bottom=10),
                ),
                device_list,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        ),
        expand=True,
        padding=ft.padding.all(14),
    )

    right_panel = ft.Container(
        content=ft.Column(),
        width=200,
        bgcolor=BG_SECONDARY,
        border=ft.border.only(left=ft.BorderSide(1, BORDER)),
    )

    page.add(
        ft.Row(
            controls=[left_panel, middle_panel, right_panel],
            spacing=0,
            expand=True,
        )
    )


def _cleanup_on_exit():
    """关窗口时：通知后端 shutdown → 杀 adb server → 退出。"""
    try:
        requests.post(f"{API_BASE}/api/shutdown", timeout=5)
    except Exception:
        pass
    try:
        _adb = _find_adb()
        if _adb:
            subprocess.run([_adb, "kill-server"], timeout=10,
                           creationflags=_WIN_FLAGS,
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _find_adb():
    """找 adb.exe 路径（兼容 PyInstaller 和开发模式）。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        path = os.path.join(base, "adb.exe")
        if os.path.isfile(path):
            return path
        path = os.path.join(sys._MEIPASS, "adb.exe")
        if os.path.isfile(path):
            return path
    # 开发模式：尝试 PATH
    import shutil
    return shutil.which("adb") or "adb"

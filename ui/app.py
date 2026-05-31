"""momoqun 桌面主窗口 — Neon Aurora 控制中心布局。

设计特色：
  - 纯黑背景配极光青光效
  - 聚光灯般的发光边框
  - 新拟态柔和阴影
  - 渐变文字和图标
"""

import flet as ft
import requests
import subprocess
import sys
import os
import atexit

from ui.theme import (
    apply_theme, BG, BG_CARD, BG_SURFACE, BG_GLOW, BORDER, DIVIDER, BORDER_GLOW,
    TEXT, TEXT_SECONDARY, TEXT_MUTED, TEXT_ACCENT,
    ACCENT, ACCENT_DIM, ACCENT_GLOW, DANGER, DANGER_DIM,
    CARD_RADIUS, ICON_RADIUS,
    accent_btn, danger_btn, section_title, separator, glow_divider,
    logo, logo_with_text,
)
from ui.adb_panel import ADBPanel
from ui.account_check_panel import AccountCheckPanel
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
    page.window_width = 1480
    page.window_height = 1000
    page.window_min_width = 1100
    page.window_min_height = 750
    page.padding = 0
    apply_theme(page)

    page.on_window_destroy = lambda _: _cleanup()

    # ── 组件 ──
    dev = DeviceList(page)
    adb = ADBPanel(device_list=dev)
    cfg = ConfigPanel()
    log = LogArea()
    acc = AccountCheckPanel(page)

    cfg.load()

    # ── 标题栏 - 聚光灯效果 ──
    title_bar = ft.Container(
        content=ft.Row([
            logo_with_text(22),
            ft.Row([
                ft.Container(
                    content=ft.Row([
                        ft.Text("v1.0", size=12, color=TEXT_MUTED, weight="w600"),
                    ]),
                    bgcolor=BG_CARD,
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=14, vertical=6),
                    border=ft.border.all(1, BORDER),
                ),
                danger_btn("安全退出", lambda _: (_cleanup(), page.update()), height=38),
            ], spacing=16),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=BG_SURFACE,
        padding=ft.padding.symmetric(horizontal=28, vertical=16),
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=30,
            color=ACCENT_GLOW,
            offset=ft.Offset(0, 2),
        ),
    )

    # ── 左侧面板（ADB + 配置） ──
    left_panel = ft.Container(
        content=ft.Column([
            # ADB 管理区
            ft.Container(
                content=adb.build(),
                margin=ft.margin.only(bottom=12),
            ),
            # 配置区（可滚动）
            ft.Container(
                content=cfg.build(),
                expand=True,
            ),
        ], spacing=0, expand=True),
        width=380,
        bgcolor=BG_SURFACE,
        border=ft.border.only(right=ft.BorderSide(1, BORDER)),
    )

    # ── 右侧主区域（设备列表） ──
    right_panel = ft.Container(
        content=ft.Column([
            # 设备列表标题
            ft.Container(
                content=ft.Row([
                    section_title("已添加设备", ft.Icons.DEVICE_HUB),
                    ft.Container(
                        content=ft.Text(ref=dev.count, size=13, color=TEXT_MUTED, weight="w600"),
                        bgcolor=BG_CARD,
                        border_radius=10,
                        padding=ft.padding.symmetric(horizontal=14, vertical=6),
                        border=ft.border.all(1, BORDER),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=ft.padding.symmetric(horizontal=32, vertical=18),
            ),
            # 设备卡片列表
            ft.Container(
                content=dev.build(),
                expand=True,
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
        ], spacing=0, expand=True),
        expand=True,
        bgcolor=BG,
    )

    # ── 右侧第三列：账号检测 ──
    account_panel = acc.build()

    # ── 控件区 ──
    controls_row = ft.Row(
        controls=[left_panel, right_panel, account_panel],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ── 日志区 ──
    log_area = ft.Container(
        content=log.build(),
        bgcolor=BG_SURFACE,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=30,
            color=ACCENT_GLOW,
            offset=ft.Offset(0, -2),
        ),
    )

    # ── 顶级容器 ──
    page.add(
        ft.Column(
            controls=[title_bar, controls_row, log_area],
            expand=True,
            spacing=0,
        )
    )

    # ── 启动轮询 ──
    try:
        dev.did_mount()
    except Exception:
        pass
    try:
        acc.did_mount()
    except Exception:
        pass

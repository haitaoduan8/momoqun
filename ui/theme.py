"""momoqun 深灰色主题色板。"""

import flet as ft

# 深灰色系（不用纯黑）
BG = "#1a1a2e"
BG_SURFACE = "#1e1e32"
BG_CARD = "#252540"
BG_ELEVATED = "#2d2d4a"
BG_HOVER = "#35355a"

BORDER = "#3a3a5c"
DIVIDER = "#3a3a5c"

TEXT = "#e0e0f0"
TEXT_SECONDARY = "#9e9eb8"
TEXT_MUTED = "#707088"

ACCENT = "#7c8cf8"
ACCENT_HOVER = "#9aa5ff"
SUCCESS = "#4ade80"
WARNING = "#fbbf24"
DANGER = "#f87171"

RUNNING_GREEN = "#4ade80"
STOPPED_GRAY = "#707088"
PAUSED_YELLOW = "#fbbf24"
ERROR_RED = "#f87171"

BTN_RADIUS = 8
CARD_RADIUS = 12


def apply_theme(page: ft.Page):
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.spacing = 0
    page.window_bgcolor = BG


def state_color(state: str) -> str:
    return {
        "running": RUNNING_GREEN,
        "paused": PAUSED_YELLOW,
        "error": ERROR_RED,
    }.get(state, STOPPED_GRAY)


def state_label(state: str) -> str:
    return {
        "running": "🟢 运行中",
        "paused": "🟡 已暂停",
        "error": "🔴 错误",
    }.get(state, "⚫ 已停止")

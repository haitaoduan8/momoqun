"""momoqun Notion 暖暗色板 — whisper 边界替代阴影。"""

import flet as ft

# ── 背景层次（暖暗底，不偏蓝不偏紫） ──
BG = "#1A1A1A"
BG_SURFACE = "#222222"
BG_CARD = "#282828"
BG_ELEVATED = "#2E2E2E"
BG_HOVER = "#363636"

# ── 边界（whisper — 几乎不可见的边界替代阴影） ──
BORDER = "rgba(255,255,255,0.07)"
DIVIDER = "rgba(255,255,255,0.06)"

# ── 文字（暖白，不是冷白） ──
TEXT = "#E8E8E4"
TEXT_SECONDARY = "#9B9B96"
TEXT_MUTED = "#6B6B66"

# ── 强调色（Notion Blue） ──
ACCENT = "#2383E2"
ACCENT_HOVER = "#3395F0"
SUCCESS = "#2EA043"
WARNING = "#D29922"
DANGER = "#F85149"

# ── 设备状态色 ──
RUNNING_GREEN = "#2EA043"
STOPPED_GRAY = "#6B6B66"
PAUSED_YELLOW = "#D29922"
ERROR_RED = "#F85149"

# ── 几何 ──
BTN_RADIUS = 6
CARD_RADIUS = 10
INPUT_RADIUS = 6


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
        "running": "运行中",
        "paused": "已暂停",
        "error": "错误",
    }.get(state, "已停止")

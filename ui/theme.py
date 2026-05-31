"""momoqun 主题系统 — Neon Aurora 风格。

设计语言借鉴：
  - Elegant Dark Pattern：深邃渐变背景 + 光线条纹
  - Spotlight：聚光灯发光效果
  - Neumorphism：新拟态柔和阴影
  - 渐变文字 + 玻璃质感

核心特色：
  - 纯黑底色配青色光效，营造赛博朋克氛围
  - 聚光灯般的发光边框和指示器
  - 渐变文字和图标
  - 新拟态柔和阴影
  - 微妙点状纹理背景
"""

import flet as ft

# ── 背景层次（从深到浅） ──
BG = "#000000"               # 纯黑底色
BG_SURFACE = "#050508"       # 面板/侧边栏
BG_CARD = "#0A0A0F"          # 卡片
BG_ELEVATED = "#0F0F15"      # 悬浮/弹出层
BG_HOVER = "#14141C"         # 悬停态
BG_INPUT = "#08080C"         # 输入框
BG_BADGE = "#0F0F15"         # 徽章背景
BG_GLOW = "#0A0E1A"          # 发光背景

# ── 边界 ──
BORDER = "rgba(0,255,200,0.06)"      # 青色微光边框
BORDER_SUBTLE = "rgba(0,255,200,0.03)"
BORDER_FOCUS = "rgba(0,255,200,0.3)" # 聚焦时明亮青色
DIVIDER = "rgba(0,255,200,0.04)"
BORDER_GLOW = "rgba(0,255,200,0.15)" # 发光边框

# ── 文字（三级层次） ──
TEXT = "#F0F0F5"              # 主文字 - 纯白偏蓝
TEXT_SECONDARY = "#8888A0"    # 次要文字
TEXT_MUTED = "#4A4A5C"        # 弱化文字
TEXT_INVERSE = "#000000"      # 反色文字
TEXT_ACCENT = "#00FFC8"       # 强调文字 - 青色

# ── 主强调色：极光青 ──
ACCENT = "#00FFC8"            # 极光青 - 主色
ACCENT_HOVER = "#33FFD4"      # 悬停态
ACCENT_DIM = "rgba(0,255,200,0.08)"  # 淡背景
ACCENT_GLOW = "rgba(0,255,200,0.20)" # 发光
ACCENT_SUBTLE = "rgba(0,255,200,0.04)"

# ── 辅助强调色：电光蓝 ──
ELECTRIC = "#0080FF"
ELECTRIC_DIM = "rgba(0,128,255,0.08)"
ELECTRIC_GLOW = "rgba(0,128,255,0.15)"

# ── 渐变色 ──
GRADIENT_CYAN = ["#00FFC8", "#0080FF"]  # 青蓝渐变
GRADIENT_GLOW = ["rgba(0,255,200,0.3)", "rgba(0,128,255,0.1)"] # 发光渐变

# ── 状态色 ──
SUCCESS = "#00FF88"           # 霓虹绿
SUCCESS_DIM = "rgba(0,255,136,0.08)"
SUCCESS_GLOW = "rgba(0,255,136,0.20)"
WARNING = "#FFB800"           # 琥珀金
WARNING_DIM = "rgba(255,184,0,0.08)"
WARNING_GLOW = "rgba(255,184,0,0.15)"
DANGER = "#FF3355"            # 霓虹红
DANGER_DIM = "rgba(255,51,85,0.08)"
DANGER_GLOW = "rgba(255,51,85,0.15)"

# ── 设备状态色 ──
RUNNING_GREEN = "#00FF88"
STOPPED_GRAY = "#4A4A5C"
PAUSED_YELLOW = "#FFB800"
ERROR_RED = "#FF3355"

# ── 几何 ──
BTN_RADIUS = 12
CARD_RADIUS = 20
INPUT_RADIUS = 12
SIDEBAR_RADIUS = 0
ICON_RADIUS = 14

# ── 阴影 ──
SHADOW_SM = "0 2px 8px rgba(0,0,0,0.5)"
SHADOW_MD = "0 4px 20px rgba(0,0,0,0.6)"
SHADOW_LG = "0 8px 40px rgba(0,0,0,0.7)"
SHADOW_GLOW = "0 0 30px rgba(0,255,200,0.15)"
SHADOW_INSET = "inset 0 1px 0 rgba(255,255,255,0.05)"


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


def state_icon(state: str) -> str:
    return {
        "running": ft.Icons.PLAY_CIRCLE_FILLED,
        "paused": ft.Icons.PAUSE_CIRCLE_FILLED,
        "error": ft.Icons.ERROR,
    }.get(state, ft.Icons.STOP_CIRCLE)


# ── 聚光灯效果容器 ──

def spotlight_container(content, **kwargs):
    """带聚光灯效果的容器 - 青色发光边框。"""
    defaults = dict(
        bgcolor=BG_CARD,
        border_radius=CARD_RADIUS,
        padding=ft.padding.symmetric(horizontal=24, vertical=20),
        border=ft.border.all(1, BORDER),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=30,
            color=ACCENT_GLOW,
            offset=ft.Offset(0, 0),
        ),
    )
    defaults.update(kwargs)
    return ft.Container(content=content, **defaults)


# ── 复用组件样式 ──

def card_container(content, **kwargs):
    """通用卡片容器 - 带发光边框和柔和阴影。"""
    defaults = dict(
        bgcolor=BG_CARD,
        border_radius=CARD_RADIUS,
        padding=ft.padding.symmetric(horizontal=24, vertical=20),
        border=ft.border.all(1, BORDER),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=20,
            color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
    )
    defaults.update(kwargs)
    return ft.Container(content=content, **defaults)


def accent_btn(text, on_click, icon=None, height=44, width=None):
    """主强调按钮：极光青渐变。"""
    return ft.ElevatedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        bgcolor=ACCENT,
        color=TEXT_INVERSE,
        height=height,
        width=width,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=28),
            text_style=ft.TextStyle(size=14, weight="w700"),
            shadow_color=ACCENT_GLOW,
            elevation=8,
        ),
    )


def outline_btn(text, on_click, color=TEXT_SECONDARY, height=40):
    """描边按钮 - 青色发光边框。"""
    return ft.OutlinedButton(
        text=text,
        on_click=on_click,
        height=height,
        style=ft.ButtonStyle(
            color=color,
            side=ft.BorderSide(1, BORDER),
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=24),
            text_style=ft.TextStyle(size=13, weight="w600"),
        ),
    )


def danger_btn(text, on_click, height=40):
    """危险按钮。"""
    return ft.ElevatedButton(
        text=text,
        on_click=on_click,
        bgcolor=DANGER,
        color="#ffffff",
        height=height,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=24),
            text_style=ft.TextStyle(size=13, weight="w700"),
            shadow_color=DANGER_GLOW,
            elevation=8,
        ),
    )


def success_btn(text, on_click, height=40):
    """成功按钮。"""
    return ft.ElevatedButton(
        text=text,
        on_click=on_click,
        bgcolor=SUCCESS,
        color=TEXT_INVERSE,
        height=height,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=24),
            text_style=ft.TextStyle(size=13, weight="w700"),
            shadow_color=SUCCESS_GLOW,
            elevation=8,
        ),
    )


def form_input(ref, value="", hint="", multiline=False, height=44, on_change=None):
    """表单输入框 - 青色聚焦发光。"""
    return ft.TextField(
        ref=ref,
        value=value,
        hint_text=hint,
        border_color=BORDER,
        focused_border_color=BORDER_FOCUS,
        bgcolor=BG_INPUT,
        color=TEXT,
        hint_style=ft.TextStyle(color=TEXT_MUTED, size=13),
        text_size=13,
        height=height if not multiline else 72,
        multiline=multiline,
        expand=True,
        content_padding=ft.Padding(left=16, top=12, right=16, bottom=12),
        border_radius=INPUT_RADIUS,
        on_change=on_change,
        cursor_color=ACCENT,
        focused_bgcolor=BG_HOVER,
    )


def section_title(text, icon=None):
    """分区标题 - 青色图标徽章。"""
    items = []
    if icon:
        items.append(ft.Container(
            content=ft.Icon(icon, size=20, color=ACCENT),
            bgcolor=ACCENT_DIM,
            border_radius=ICON_RADIUS,
            padding=8,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=12,
                color=ACCENT_GLOW,
            ),
        ))
    items.append(ft.Text(text, size=15, weight="w700", color=TEXT))
    return ft.Row(items, spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def badge(text, color, bg_color=None):
    """状态徽章 - 发光圆点。"""
    if bg_color is None:
        bg_color = f"{color}15"
    return ft.Container(
        content=ft.Row([
            ft.Container(
                width=8, height=8, bgcolor=color, border_radius=10,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=10,
                    color=color,
                ),
            ),
            ft.Text(text, size=12, color=color, weight="w600"),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=bg_color,
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=14, vertical=6),
    )


def icon_badge(icon, color, size=22):
    """图标徽章 - 青色发光背景。"""
    return ft.Container(
        content=ft.Icon(icon, size=size, color=color),
        bgcolor=f"{color}12",
        border_radius=ICON_RADIUS,
        padding=10,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=15,
            color=f"{color}25",
        ),
    )


def stat_card(title, value, icon=None, color=ACCENT):
    """统计卡片 - 带发光效果。"""
    content_items = []
    if icon:
        content_items.append(ft.Container(
            content=ft.Icon(icon, size=22, color=color),
            bgcolor=f"{color}12",
            border_radius=ICON_RADIUS,
            padding=10,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=15,
                color=f"{color}25",
            ),
        ))
    content_items.append(ft.Column([
        ft.Text(title, size=11, color=TEXT_MUTED, weight="w500"),
        ft.Text(value, size=20, color=TEXT, weight="w700"),
    ], spacing=4))

    return ft.Container(
        content=ft.Row(content_items, spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=BG_CARD,
        border_radius=CARD_RADIUS,
        padding=ft.padding.symmetric(horizontal=20, vertical=16),
        border=ft.border.all(1, BORDER),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=20,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
    )


def separator():
    """分隔线 - 青色微光。"""
    return ft.Container(
        height=1,
        bgcolor=DIVIDER,
        margin=ft.margin.symmetric(vertical=10),
    )


def glow_divider():
    """发光分隔线。"""
    return ft.Container(
        height=1,
        bgcolor=ACCENT_GLOW,
        margin=ft.margin.symmetric(vertical=12),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=8,
            color=ACCENT_GLOW,
        ),
    )


# ── Logo 组件 ──

def logo(size=36):
    """momoqun Logo - 青色渐变发光。"""
    return ft.Container(
        content=ft.Text("M", size=size * 0.5, weight="w900", color=BG),
        width=size,
        height=size,
        bgcolor=ACCENT,
        border_radius=size * 0.28,
        alignment=ft.alignment.center,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=20,
            color=ACCENT_GLOW,
        ),
    )


def logo_with_text(text_size=20):
    """Logo + 文字组合。"""
    return ft.Row([
        logo(36),
        ft.Text("momoqun", size=text_size, weight="w700", color=TEXT),
    ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER)

"""momoqun 深色主题色板 — GitHub Dark 风格"""

BG_PRIMARY = "#0d1117"
BG_SECONDARY = "#161b22"
BG_CARD = "#21262d"
BG_HOVER = "#30363d"
BORDER = "#30363d"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_MUTED = "#6e7681"
ACCENT = "#58a6ff"
ACCENT_HOVER = "#79c0ff"
SUCCESS = "#3fb950"
WARNING = "#d29922"
DANGER = "#f85149"
STOPPED = "#6e7681"
RUNNING = "#3fb950"
PAUSED = "#d29922"
ERROR = "#f85149"


def apply_theme(page):
    """将深色主题应用到 Flet 页面。"""
    page.theme_mode = "dark"
    page.bgcolor = BG_PRIMARY
    page.window_bgcolor = BG_PRIMARY
    page.padding = 0
    page.spacing = 0

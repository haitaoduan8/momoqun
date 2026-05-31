"""日志输出区 — Neon Aurora 风格，终端风格折叠面板。"""

import flet as ft
from ui.theme import (
    BG, BG_CARD, BG_ELEVATED, BORDER, BORDER_GLOW, DIVIDER,
    TEXT, TEXT_SECONDARY, TEXT_MUTED, TEXT_ACCENT,
    ACCENT, ACCENT_DIM, ACCENT_GLOW, SUCCESS, DANGER,
    CARD_RADIUS, ICON_RADIUS,
)

MAX_LINES = 500


class LogArea:
    def __init__(self):
        self.log = ft.Ref[ft.ListView]()
        self._expanded = False
        self._toggle_icon = ft.Ref[ft.Icon]()
        self._content = ft.Ref[ft.Container]()
        self._badge = ft.Ref[ft.Container]()

    def build(self):
        header = ft.GestureDetector(
            content=ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ref=self._toggle_icon,
                        name=ft.Icons.KEYBOARD_ARROW_RIGHT,
                        size=22,
                        color=TEXT_MUTED,
                    ),
                    ft.Container(
                        content=ft.Icon(ft.Icons.CODE, size=20, color=ACCENT),
                        bgcolor=ACCENT_DIM,
                        border_radius=ICON_RADIUS,
                        padding=8,
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=12,
                            color=ACCENT_GLOW,
                        ),
                    ),
                    ft.Text("运行日志", size=14, weight="w700", color=TEXT_ACCENT),
                    ft.Container(expand=True),
                    ft.Container(
                        ref=self._badge,
                        content=ft.Text("0", size=11, color=TEXT_MUTED, weight="w600"),
                        bgcolor=BG_ELEVATED,
                        border_radius=10,
                        padding=ft.padding.symmetric(horizontal=12, vertical=5),
                        visible=True,
                        border=ft.border.all(1, BORDER),
                    ),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=28, vertical=16),
                bgcolor=BG_CARD,
                border=ft.border.only(top=ft.BorderSide(1, BORDER)),
            ),
            on_tap=self._toggle,
        )

        return ft.Column([
            header,
            ft.Container(
                ref=self._content,
                content=ft.Container(
                    content=ft.ListView(
                        ref=self.log,
                        controls=[],
                        spacing=1,
                        auto_scroll=True,
                    ),
                    bgcolor="#020204",
                    border_radius=CARD_RADIUS,
                    padding=ft.padding.all(20),
                    height=240,
                    border=ft.border.all(1, BORDER),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=25,
                        color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                        offset=ft.Offset(0, 6),
                    ),
                ),
                padding=ft.padding.only(left=28, right=28, bottom=20),
                visible=False,
            ),
        ], spacing=0)

    def _toggle(self, e):
        self._expanded = not self._expanded
        self._toggle_icon.current.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN if self._expanded
            else ft.Icons.KEYBOARD_ARROW_RIGHT
        )
        self._content.current.visible = self._expanded
        self._toggle_icon.current.update()
        self._content.current.update()

    def append(self, text: str, color: str = TEXT_SECONDARY):
        try:
            ctrls = self.log.current.controls
            ctrls.append(ft.Text(text, size=12, color=color, font_family="monospace",
                                 selectable=True, weight="w500"))
            if len(ctrls) > MAX_LINES:
                ctrls = ctrls[-MAX_LINES:]
            try:
                self._badge.current.content.value = str(len(ctrls))
                self._badge.current.content.update()
            except Exception:
                pass
            self.log.current.update()
        except Exception:
            pass

    def append_info(self, text: str):
        self.append(text, TEXT_SECONDARY)

    def append_success(self, text: str):
        self.append(text, SUCCESS)

    def append_error(self, text: str):
        self.append(text, DANGER)

    def clear(self):
        try:
            self.log.current.controls.clear()
            self._badge.current.content.value = "0"
            self._badge.current.content.update()
            self.log.current.update()
        except Exception:
            pass

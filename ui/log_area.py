"""日志输出区 — 默认折叠，点击标题展开，滚动追加。"""

import flet as ft
from ui.theme import BG_CARD, BORDER, TEXT, TEXT_SECONDARY, TEXT_MUTED

MAX_LINES = 500


class LogArea:
    """日志输出面板。外部可调用 append(text, color) 追加。"""

    def __init__(self):
        self.log = ft.Ref[ft.ListView]()
        self._expanded = False
        self._toggle_icon = ft.Ref[ft.Icon]()
        self._content = ft.Ref[ft.Container]()

    def build(self):
        # 标题行 — 点击切换展开/折叠
        header = ft.GestureDetector(
            content=ft.Row([
                ft.Icon(
                    ref=self._toggle_icon,
                    name="chevron_right",
                    size=18,
                    color=TEXT_SECONDARY,
                ),
                ft.Text("运行日志", size=14, weight="bold", color=TEXT),
            ], spacing=6),
            on_tap=self._toggle,
        )

        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    header,
                    ft.Container(
                        ref=self._content,
                        content=ft.Column([
                            ft.Divider(height=1, color=BORDER),
                            ft.Container(
                                content=ft.ListView(
                                    ref=self.log,
                                    controls=[],
                                    spacing=2,
                                    auto_scroll=True,
                                ),
                                expand=True,
                            ),
                        ], spacing=6),
                        visible=False,
                        expand=True,
                    ),
                ], spacing=8),
                padding=ft.padding.only(left=16, top=12, right=16, bottom=12),
            ),
            color=BG_CARD,
            elevation=0,
            margin=ft.margin.only(top=10),
        )

    def _toggle(self, e):
        self._expanded = not self._expanded
        self._toggle_icon.current.name = (
            "expand_more" if self._expanded else "chevron_right"
        )
        self._content.current.visible = self._expanded
        self._toggle_icon.current.update()
        self._content.current.update()

    def append(self, text: str, color: str = TEXT_SECONDARY):
        try:
            ctrls = self.log.current.controls
            ctrls.append(ft.Text(text, size=12, color=color, font_family="monospace"))
            if len(ctrls) > MAX_LINES:
                ctrls = ctrls[-MAX_LINES:]
            self.log.current.update()
        except Exception:
            pass

    def append_info(self, text: str):
        self.append(text, TEXT_SECONDARY)

    def append_success(self, text: str):
        self.append(text, "#4ade80")

    def append_error(self, text: str):
        self.append(text, "#f87171")

    def clear(self):
        try:
            self.log.current.controls.clear()
            self.log.current.update()
        except Exception:
            pass

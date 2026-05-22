"""配置面板：全部配置项（可折叠）+ 保存按钮。"""

import flet as ft
import threading
import requests
import yaml
from ui.theme import (
    BG_SECONDARY, BG_CARD, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, SUCCESS, DANGER,
)

API_BASE = "http://localhost:5100"

POOL_LABELS = ["池1-破冰", "池2", "池3", "池4", "池5"]


class ConfigPanel(ft.UserControl):
    def __init__(self):
        super().__init__()
        self._status = ft.Ref[ft.Text]()
        self._fields: dict[str, ft.Ref[ft.TextField]] = {}
        self._pool_fields: dict[int, ft.Ref[ft.TextField]] = {}

    def build(self):
        for key in [
            "group_name", "chat_rounds_before_follow", "max_chat_rounds",
            "round_end_wait_s", "chat_round_wait_s", "greet_scan_interval_s",
            "invite_back_message", "max_consecutive_errors",
            "reply_interval_min", "reply_interval_max",
        ]:
            self._fields[key] = ft.Ref[ft.TextField]()

        for i in range(1, 6):
            self._pool_fields[i] = ft.Ref[ft.TextField]()

        self._status_col = ft.Text(ref=self._status, size=12, color=TEXT_SECONDARY)

        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        [ft.Text("配置", size=13, color=TEXT_PRIMARY, weight="bold")],
                    ),
                ),
                ft.Container(
                    content=ft.Column(
                        controls=self._build_form() + [
                            ft.Divider(height=1, color=BORDER),
                            ft.Row([
                                ft.ElevatedButton(
                                    "保存配置", on_click=self._do_save,
                                    bgcolor=ACCENT, color="#ffffff",
                                    height=34,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                                ),
                                self._status_col,
                            ]),
                        ],
                        spacing=6,
                    ),
                    padding=ft.padding.all(10),
                    bgcolor=BG_SECONDARY,
                    border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
                ),
            ],
        )

    def _build_form(self):
        return [
            self._row("群聊名称", "group_name", "我的群聊"),
            self._row("聊N轮后关注", "chat_rounds_before_follow", "3"),
            self._row("最大聊天轮数", "max_chat_rounds", "10"),
            self._row("轮次间隔(秒)", "round_end_wait_s", "10"),
            self._row("回复等待(秒)", "chat_round_wait_s", "30"),
            self._row("招呼扫描间隔", "greet_scan_interval_s", "5"),
            self._row("回关邀请话术", "invite_back_message", "关注我互关拉你进群"),
            self._row("最大连续错误", "max_consecutive_errors", "5"),
            self._row("回复间隔(秒)", "reply_interval_min", "1"),
            self._row("回复间隔~", "reply_interval_max", "3"),
            ft.Text("消息池配置", size=12, color=TEXT_SECONDARY, weight="bold"),
            *[self._pool_row(i) for i in range(1, 6)],
        ]

    def _row(self, label, key, placeholder):
        return ft.Row([
            ft.Text(label, size=12, color=TEXT_SECONDARY, width=100),
            ft.TextField(
                ref=self._fields[key],
                value=placeholder,
                border_color=BORDER,
                bgcolor=BG_CARD,
                color=TEXT_PRIMARY,
                text_size=12,
                height=32,
                content_padding=ft.padding.only(left=8, right=8),
            ),
        ], spacing=6)

    def _pool_row(self, idx):
        return ft.Row([
            ft.Text(POOL_LABELS[idx - 1], size=12, color=TEXT_SECONDARY, width=100),
            ft.TextField(
                ref=self._pool_fields[idx],
                value="",
                border_color=BORDER,
                bgcolor=BG_CARD,
                color=TEXT_PRIMARY,
                text_size=12,
                height=60,
                multiline=True,
                content_padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
                hint_text="每行一条话术",
            ),
        ], spacing=6)

    # ─── 加载配置 ───

    def load(self):
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        try:
            r = requests.get(f"{API_BASE}/api/config", timeout=10)
            cfg = r.json()

            mapping = {
                "group_name": ("group_name", ""),
                "chat_rounds_before_follow": ("chat_rounds_before_follow", "3"),
                "max_chat_rounds": ("max_chat_rounds", "10"),
                "round_end_wait_s": ("round_end_wait_s", "10"),
                "chat_round_wait_s": ("chat_round_wait_s", "30"),
                "greet_scan_interval_s": ("greet_scan_interval_s", "5"),
                "invite_back_message": ("invite_back_message", ""),
                "max_consecutive_errors": ("max_consecutive_errors", "5"),
            }

            for field_key, (cfg_key, default) in mapping.items():
                val = cfg.get(cfg_key, default)
                if val is not None:
                    self._fields[field_key].current.value = str(val)
                    self._fields[field_key].current.update()

            # reply_interval
            ri = cfg.get("reply_interval", {})
            for k, fk in [("min", "reply_interval_min"), ("max", "reply_interval_max")]:
                val = ri.get(k, "")
                if val:
                    self._fields[fk].current.value = str(val)
                    self._fields[fk].current.update()

            # message_pools
            pools = cfg.get("message_pools", [])
            for pool in pools:
                pid = pool.get("id", 0)
                if pid in self._pool_fields:
                    msgs = pool.get("messages", [])
                    self._pool_fields[pid].current.value = "\n".join(msgs)
                    self._pool_fields[pid].current.update()

            self._set_status("配置已加载", SUCCESS)
        except Exception as ex:
            self._set_status(f"加载失败: {ex}", DANGER)

    # ─── 保存配置 ───

    def _do_save(self, e):
        threading.Thread(target=self._save_thread, daemon=True).start()

    def _save_thread(self):
        try:
            cfg = {
                "group_name": self._get("group_name"),
                "chat_rounds_before_follow": int(self._get("chat_rounds_before_follow", "3")),
                "max_chat_rounds": int(self._get("max_chat_rounds", "10")),
                "round_end_wait_s": float(self._get("round_end_wait_s", "10")),
                "chat_round_wait_s": float(self._get("chat_round_wait_s", "30")),
                "greet_scan_interval_s": float(self._get("greet_scan_interval_s", "5")),
                "invite_back_message": self._get("invite_back_message"),
                "max_consecutive_errors": int(self._get("max_consecutive_errors", "5")),
                "reply_interval": {
                    "min": float(self._get("reply_interval_min", "1")),
                    "max": float(self._get("reply_interval_max", "3")),
                },
                "message_pools": [],
                "message_pool_rotation": {"strategy": "sequential"},
                "chat_strategy": "message_pool",
                "chat_list_scan_interval": {"min": 2.0, "max": 4.0},
                "click_offset": {"x": 5, "y": 5},
                "delay": {"min": 0.3, "max": 0.8},
                "chat_ignore_names": ["互动通知", "订阅内容", "陌陌", "超级抢车位", "猜你喜欢", "谁看过我"],
            }

            for i in range(1, 6):
                msgs = [m.strip() for m in self._pool_fields[i].current.value.split("\n") if m.strip()]
                if msgs:
                    cfg["message_pools"].append({"id": i, "messages": msgs})

            r = requests.put(f"{API_BASE}/api/config",
                             json={"config": cfg}, timeout=10)
            d = r.json()
            if d.get("ok"):
                self._set_status("保存成功", SUCCESS)
            else:
                self._set_status(d.get("error", "保存失败"), DANGER)
        except Exception as ex:
            self._set_status(f"保存失败: {ex}", DANGER)

    def _get(self, key, default=""):
        try:
            return self._fields[key].current.value or default
        except Exception:
            return default

    def _set_status(self, msg, color):
        try:
            self._status.current.value = msg
            self._status.current.color = color
            self._status.current.update()
            self._status_col.update()
        except Exception:
            pass

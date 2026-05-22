"""配置面板 — Card 包裹全配置项 + 消息池 + 保存。"""

import flet as ft
import threading
import requests
from ui.theme import (
    BG_CARD, BG_ELEVATED, BORDER, TEXT, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, DANGER, BTN_RADIUS,
)

API = "http://localhost:5100"
POOL_NAMES = ["池1-破冰", "池2", "池3", "池4", "池5"]


def _field(label, ref, val="", hint="", multiline=False, height=36):
    return ft.Row([
        ft.Text(label, size=13, color=TEXT_SECONDARY, width=100),
        ft.TextField(
            ref=ref,
            value=val,
            hint_text=hint,
            border_color=BORDER,
            bgcolor=BG_ELEVATED,
            color=TEXT,
            text_size=13,
            height=height if not multiline else 64,
            multiline=multiline,
            content_padding=ft.padding.only(left=10, right=10, top=6, bottom=6),
        ),
    ], spacing=8)


class ConfigPanel:
    def __init__(self):
        self.fields: dict[str, ft.Ref[ft.TextField]] = {}
        self.pools: dict[int, ft.Ref[ft.TextField]] = {}
        self.status = ft.Ref[ft.Text]()

        for k in [
            "group_name", "chat_rounds_before_follow", "max_chat_rounds",
            "round_end_wait_s", "chat_round_wait_s", "greet_scan_interval_s",
            "invite_back_message", "max_consecutive_errors",
            "reply_min", "reply_max",
        ]:
            self.fields[k] = ft.Ref[ft.TextField]()
        for i in range(1, 6):
            self.pools[i] = ft.Ref[ft.TextField]()

    def build(self):
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("配置", size=15, weight="bold", color=TEXT),
                    ft.Divider(height=1, color=BORDER),

                    _field("群聊名称", self.fields["group_name"], "我的群聊"),
                    _field("聊N轮后关注", self.fields["chat_rounds_before_follow"], "3"),
                    _field("最大聊天轮数", self.fields["max_chat_rounds"], "10"),
                    _field("轮次间隔(秒)", self.fields["round_end_wait_s"], "10"),
                    _field("回复等待(秒)", self.fields["chat_round_wait_s"], "30"),
                    _field("招呼扫描间隔", self.fields["greet_scan_interval_s"], "5"),
                    _field("回关邀请话术", self.fields["invite_back_message"], "互关拉你进群"),
                    _field("最大连续错误", self.fields["max_consecutive_errors"], "5"),
                    _field("回复间隔(秒)", self.fields["reply_min"], "1"),
                    _field("回复间隔~", self.fields["reply_max"], "3"),

                    ft.Divider(height=1, color=BORDER),
                    ft.Text("消息池", size=14, weight="bold", color=TEXT),
                    *[_field(POOL_NAMES[i-1], self.pools[i], multiline=True, height=56) for i in range(1, 6)],

                    ft.Divider(height=1, color=BORDER),
                    ft.Row([
                        ft.ElevatedButton(
                            "保存配置", on_click=self._save,
                            bgcolor=ACCENT, color="#ffffff", height=38,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
                                padding=ft.padding.symmetric(horizontal=20),
                            ),
                        ),
                        ft.Text(ref=self.status, size=13, color=TEXT_SECONDARY),
                    ], spacing=10),
                ], spacing=8),
                padding=20,
            ),
            color=BG_CARD,
            elevation=2,
            margin=10,
        )

    def load(self):
        threading.Thread(target=self._ld, daemon=True).start()

    def _ld(self):
        try:
            r = requests.get(f"{API}/api/config", timeout=10)
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

            for fk, (ck, dv) in mapping.items():
                v = cfg.get(ck, dv)
                if v is not None:
                    self.fields[fk].current.value = str(v)
                    self.fields[fk].current.update()

            ri = cfg.get("reply_interval", {})
            self.fields["reply_min"].current.value = str(ri.get("min", "1"))
            self.fields["reply_min"].current.update()
            self.fields["reply_max"].current.value = str(ri.get("max", "3"))
            self.fields["reply_max"].current.update()

            pools = cfg.get("message_pools", [])
            for p in pools:
                pid = p.get("id", 0)
                if pid in self.pools:
                    self.pools[pid].current.value = "\n".join(p.get("messages", []))
                    self.pools[pid].current.update()

            self._st("加载完成", SUCCESS)
        except Exception as ex:
            self._st(str(ex), DANGER)

    def _save(self, e):
        threading.Thread(target=self._sv, daemon=True).start()

    def _sv(self):
        try:
            cfg = {
                "group_name": self._g("group_name"),
                "chat_rounds_before_follow": int(self._g("chat_rounds_before_follow", "3")),
                "max_chat_rounds": int(self._g("max_chat_rounds", "10")),
                "round_end_wait_s": float(self._g("round_end_wait_s", "10")),
                "chat_round_wait_s": float(self._g("chat_round_wait_s", "30")),
                "greet_scan_interval_s": float(self._g("greet_scan_interval_s", "5")),
                "invite_back_message": self._g("invite_back_message"),
                "max_consecutive_errors": int(self._g("max_consecutive_errors", "5")),
                "reply_interval": {
                    "min": float(self._g("reply_min", "1")),
                    "max": float(self._g("reply_max", "3")),
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
                msgs = [m.strip() for m in self.pools[i].current.value.split("\n") if m.strip()]
                if msgs:
                    cfg["message_pools"].append({"id": i, "messages": msgs})

            r = requests.put(f"{API}/api/config", json={"config": cfg}, timeout=10)
            d = r.json()
            self._st("保存成功" if d.get("ok") else d.get("error", "失败"), SUCCESS if d.get("ok") else DANGER)
        except Exception as ex:
            self._st(str(ex), DANGER)

    def _g(self, k, d=""):
        try:
            return self.fields[k].current.value or d
        except Exception:
            return d

    def _st(self, msg, color):
        try:
            self.status.current.value = msg
            self.status.current.color = color
            self.status.current.update()
        except Exception:
            pass

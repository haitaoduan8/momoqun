"""配置面板 — 全部配置项 + 消息池增删 + 策略选择 + 保存。"""

import flet as ft
import threading
import requests
from ui.theme import (
    BG_CARD, BG_ELEVATED, BORDER, TEXT, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, DANGER, BTN_RADIUS,
)

API = "http://localhost:5100"
MAX_POOLS = 10


def _field(label, ref, val="", hint="", multiline=False, height=38):
    return ft.Row([
        ft.Text(label, size=13, color=TEXT_SECONDARY, width=90),
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
            expand=True,
            content_padding=ft.Padding(left=10, top=7, right=10, bottom=7),
        ),
    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _btn(text, on_click, bgcolor=ACCENT, height=34):
    return ft.ElevatedButton(
        text=text,
        on_click=on_click,
        bgcolor=bgcolor,
        color="#ffffff",
        height=height,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BTN_RADIUS),
            padding=ft.padding.symmetric(horizontal=14),
        ),
    )


class ConfigPanel:
    def __init__(self):
        self.fields: dict[str, ft.Ref[ft.TextField]] = {}
        self.pools: dict[int, ft.Ref[ft.TextField]] = {}
        self.status = ft.Ref[ft.Text]()
        self.pool_count = ft.Ref[ft.TextField]()
        self.strategy = ft.Ref[ft.Dropdown]()
        self.pools_container = ft.Ref[ft.Column]()
        self._pool_cnt = 5

        for k in [
            "group_name", "chat_rounds_before_follow", "max_chat_rounds",
            "round_end_wait_s", "chat_round_wait_s", "greet_scan_interval_s",
            "invite_back_message", "max_consecutive_errors",
            "reply_min", "reply_max",
        ]:
            self.fields[k] = ft.Ref[ft.TextField]()
        for i in range(1, MAX_POOLS + 1):
            self.pools[i] = ft.Ref[ft.TextField]()

    def build(self):
        form = ft.Column([
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
            ft.Text("聊天策略", size=14, weight="bold", color=TEXT),
            ft.Dropdown(
                ref=self.strategy,
                value="message_pool",
                options=[
                    ft.dropdown.Option("message_pool", "消息池模式"),
                    ft.dropdown.Option("ai", "AI 模式（预留）"),
                ],
                border_color=BORDER,
                bgcolor=BG_ELEVATED,
                color=TEXT,
                text_size=13,
            ),

            ft.Divider(height=1, color=BORDER),
            ft.Text("消息池", size=14, weight="bold", color=TEXT),
            ft.Row([
                ft.Text("消息池数量", size=13, color=TEXT_SECONDARY),
                ft.TextField(
                    ref=self.pool_count, value="5", text_size=13,
                    border_color=BORDER, bgcolor=BG_ELEVATED, color=TEXT,
                    width=60, height=34,
                    content_padding=ft.Padding(left=8, top=0, right=8, bottom=0),
                    text_align="center",
                    on_change=self._on_pool_count_changed,
                ),
                ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=SUCCESS,
                              tooltip="增加消息池", on_click=self._add_pool),
                ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_color=DANGER,
                              tooltip="减少消息池", on_click=self._remove_pool),
            ], spacing=6),

            ft.Column(ref=self.pools_container, spacing=6),

            ft.Divider(height=1, color=BORDER),
            ft.Row([
                _btn("保存配置", self._save),
                ft.Text(ref=self.status, size=13, color=TEXT_SECONDARY),
            ], spacing=10),
        ], spacing=8)

        self._rebuild_pools()

        return ft.Card(
            content=ft.Container(
                content=ft.Container(
                    content=form,
                    width=400,
                    alignment=ft.alignment.center,
                ),
                padding=20,
            ),
            color=BG_CARD,
            elevation=0,
            margin=10,
        )

    # ─── 消息池动态 ───

    def _rebuild_pools(self):
        """根据 self._pool_cnt 重建消息池字段。"""
        items = []
        for i in range(1, self._pool_cnt + 1):
            label = "池1-破冰" if i == 1 else f"池{i}"
            items.append(_field(label, self.pools[i], multiline=True, height=56))
        try:
            self.pools_container.current.controls = items
            self.pools_container.current.update()
        except Exception:
            pass

    def _on_pool_count_changed(self, e):
        try:
            n = int(self.pool_count.current.value or "5")
            n = max(1, min(n, MAX_POOLS))
            self._pool_cnt = n
            self.pool_count.current.value = str(n)
            self.pool_count.current.update()
            self._rebuild_pools()
        except Exception:
            pass

    def _add_pool(self, e):
        if self._pool_cnt < MAX_POOLS:
            self._pool_cnt += 1
            self.pool_count.current.value = str(self._pool_cnt)
            self.pool_count.current.update()
            self._rebuild_pools()

    def _remove_pool(self, e):
        if self._pool_cnt > 1:
            self.pools[self._pool_cnt].current.value = ""
            self._pool_cnt -= 1
            self.pool_count.current.value = str(self._pool_cnt)
            self.pool_count.current.update()
            self._rebuild_pools()

    # ─── 加载 / 保存 ───

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

            # 策略
            strat = cfg.get("chat_strategy", "message_pool")
            self.strategy.current.value = strat
            self.strategy.current.update()

            # 消息池
            pools = cfg.get("message_pools", [])
            cnt = len(pools) or 5
            self._pool_cnt = max(1, min(cnt, MAX_POOLS))
            self.pool_count.current.value = str(self._pool_cnt)
            self.pool_count.current.update()

            for p in pools:
                pid = p.get("id", 0)
                if 1 <= pid <= MAX_POOLS:
                    self.pools[pid].current.value = "\n".join(p.get("messages", []))
                    self.pools[pid].current.update()

            self._rebuild_pools()
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
                "chat_strategy": self.strategy.current.value or "message_pool",
                "message_pools": [],
                "message_pool_rotation": {"strategy": "sequential"},
                "chat_list_scan_interval": {"min": 2.0, "max": 4.0},
                "click_offset": {"x": 5, "y": 5},
                "delay": {"min": 0.3, "max": 0.8},
                "chat_ignore_names": ["互动通知", "订阅内容", "陌陌", "超级抢车位", "猜你喜欢", "谁看过我"],
            }
            for i in range(1, self._pool_cnt + 1):
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

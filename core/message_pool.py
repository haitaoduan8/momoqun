import json
import os
import random
import time


class MessagePoolManager:
    """
    按“轮次”顺序选择消息池，并在池内随机选择一句话术。

    - 第 1 轮 -> 池 1
    - 第 2 轮 -> 池 2
    - ... 用完循环
    """

    def __init__(self, settings_config, state_path="data/state.json"):
        self.state_path = state_path
        self.cfg = {}
        self.pools = []
        self.strategy = "sequential"
        self.reload_from_config(settings_config)
        self._ensure_state_file()

    def reload_from_config(self, settings_config):
        """刷新运行中的消息池配置，供参数面板保存后复用。"""
        cfg = settings_config or {}
        pools = cfg.get("message_pools") or []
        if not isinstance(pools, list) or len(pools) == 0:
            raise ValueError("settings.yaml 中 config.message_pools 不能为空")

        rot = cfg.get("message_pool_rotation") or {}
        strategy = (rot.get("strategy") or "sequential").strip().lower()
        if strategy not in {"sequential"}:
            raise ValueError(f"不支持的 message_pool_rotation.strategy: {strategy}")

        self.cfg = cfg
        self.pools = pools
        self.strategy = strategy

    def _ensure_state_file(self):
        parent = os.path.dirname(self.state_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(self.state_path):
            self._write_state({"reply_round": 0})

    def _read_state(self):
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if not isinstance(data, dict):
                return {"reply_round": 0}
            rr = data.get("reply_round")
            if not isinstance(rr, int) or rr < 0:
                rr = 0
            return {"reply_round": rr}
        except Exception:
            # 文件损坏/空文件等情况：重置
            return {"reply_round": 0}

    def _write_state(self, state):
        tmp = f"{self.state_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.state_path)

    def _pool_for_round(self, reply_round_1_based):
        idx = (reply_round_1_based - 1) % len(self.pools)
        return self.pools[idx]

    def next_message(self):
        """
        进入下一轮：轮次 +1，并返回本轮随机选中的回复内容。
        """
        state = self._read_state()
        state["reply_round"] += 1
        rr = state["reply_round"]

        pool = self._pool_for_round(rr)
        messages = pool.get("messages") if isinstance(pool, dict) else None
        if not isinstance(messages, list) or len(messages) == 0:
            raise ValueError(f"消息池为空或格式错误（第 {((rr - 1) % len(self.pools)) + 1} 个池）")

        msg = random.choice([m for m in messages if isinstance(m, str) and m.strip()])
        if not msg:
            raise ValueError("消息池 messages 中没有有效字符串")

        self._write_state(state)
        return msg

    def peek_round(self):
        """返回当前已使用到的轮次（0 表示还未开始）。"""
        return self._read_state().get("reply_round", 0)

    def get_message_for_round(self, round_n: int) -> str:
        """获取第 N 个池（1-based）中的一条随机消息，不改变内部轮次状态。

        用于按好友 chat_round 选择对应消息池的场景。
        """
        if round_n < 1:
            round_n = 1
        pool = self._pool_for_round(round_n)
        messages = pool.get("messages") if isinstance(pool, dict) else None
        if not isinstance(messages, list) or len(messages) == 0:
            raise ValueError(
                f"消息池为空或格式错误（第 {((round_n - 1) % len(self.pools)) + 1} 个池）"
            )
        msg = random.choice([m for m in messages if isinstance(m, str) and m.strip()])
        if not msg:
            raise ValueError("消息池 messages 中没有有效字符串")
        return msg

    def reset(self):
        """重置轮次为 0。"""
        self._write_state({"reply_round": 0, "reset_at": time.strftime("%Y-%m-%dT%H:%M:%S")})


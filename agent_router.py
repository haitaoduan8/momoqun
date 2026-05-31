"""APK Agent 反向 WebSocket 路由（路线 C）。

每台模拟器上的 momoqun-agent.apk 启动后主动连接 ``ws://master:<port>/agent/{serial}``，
master 用 JSON-RPC 协议下发 ``dump_hierarchy / click / swipe / type_text`` 等调用，
agent 在 AccessibilityService 进程内执行后回包。

本模块提供 3 个能力：

1. ``AgentRouter`` 单例：保存所有活跃连接 + 心跳；
2. ``AgentConnection``：单条 WebSocket 的协程封装，挂着 ``Future`` 等回包；
3. ``mount_agent_routes(app, router)``：把 ``/agent/{serial}``、``/api/agents`` 挂到 FastAPI。

业务线程（同步代码）通过 ``router.call_sync(serial, method, params, timeout=15)``
与 agent 通信；其内部走 ``asyncio.run_coroutine_threadsafe`` 桥接到事件循环。

协议详情见 ``docs/agent-protocol.md``。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


logger = logging.getLogger("agent_router")


# ---------------------------------------------------------------------------
# 错误类
# ---------------------------------------------------------------------------
class AgentError(Exception):
    """Agent 端返回的业务错误。"""

    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        super().__init__(f"agent_error code={code} msg={message}")
        self.code = code
        self.message = message
        self.data = data


class NoAgentError(AgentError):
    def __init__(self, serial: str):
        super().__init__(-32004, f"agent for serial {serial!r} not connected")
        self.serial = serial


class AgentTimeoutError(AgentError):
    def __init__(self, serial: str, method: str, timeout: float):
        super().__init__(
            -32002, f"agent {serial!r} method {method!r} timeout after {timeout}s"
        )
        self.serial = serial
        self.method = method


# ---------------------------------------------------------------------------
# 协议错误码（与 docs/agent-protocol.md 同步）
# ---------------------------------------------------------------------------
ERR_PROTOCOL = -32600           # 协议错误：消息无 id / 无 method / 字段缺失
ERR_METHOD_NOT_FOUND = -32601   # 未知方法
ERR_INVALID_PARAMS = -32602     # 参数非法
ERR_NODE_NOT_FOUND = -32001     # 元素未找到
ERR_TIMEOUT = -32002            # 操作超时
ERR_NOT_AUTHORIZED = -32003     # Accessibility 未启用 / 权限不足
ERR_AGENT_OFFLINE = -32004      # agent 未连接（master 侧合成）


# ---------------------------------------------------------------------------
# 单连接
# ---------------------------------------------------------------------------
class AgentConnection:
    """一条 agent WebSocket 的协程封装。"""

    def __init__(self, serial: str, ws: WebSocket, loop: asyncio.AbstractEventLoop):
        self.serial = serial
        self.ws = ws
        self.loop = loop
        self.connected_at = time.time()
        self.last_seen_at = self.connected_at
        # 待响应的 RPC：rpc_id → Future[dict]
        self._pending: Dict[str, asyncio.Future] = {}
        self._closed = False
        self._lock = asyncio.Lock()  # 串行化 send，避免帧交叉

    # ------------------------------------------------------------------
    # 收发
    # ------------------------------------------------------------------
    async def send_request(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> asyncio.Future:
        rpc_id = uuid.uuid4().hex
        future: asyncio.Future = self.loop.create_future()
        self._pending[rpc_id] = future
        msg = {"id": rpc_id, "method": method, "params": params or {}}
        try:
            async with self._lock:
                await self.ws.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception as exc:
            self._pending.pop(rpc_id, None)
            future.set_exception(exc)
        return future

    async def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Any:
        if self._closed:
            raise NoAgentError(self.serial)
        future = await self.send_request(method, params)
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(future_id(future, self._pending), None)
            raise AgentTimeoutError(self.serial, method, timeout)
        return result

    def handle_incoming(self, msg: dict) -> None:
        """agent → master 的单帧分发。"""
        self.last_seen_at = time.time()
        # 1) RPC 响应
        if "id" in msg and ("result" in msg or "error" in msg):
            rpc_id = msg.get("id")
            fut = self._pending.pop(rpc_id, None)
            if fut is None:
                logger.warning(
                    "agent[%s] 收到未知 rpc_id 响应: %s",
                    self.serial,
                    rpc_id,
                )
                return
            if "error" in msg:
                err = msg["error"] or {}
                fut.set_exception(
                    AgentError(
                        int(err.get("code") or -32600),
                        str(err.get("message") or "unknown"),
                        err.get("data"),
                    )
                )
            else:
                fut.set_result(msg.get("result"))
            return
        # 2) agent 主动事件
        ev = msg.get("event")
        if ev:
            logger.info("agent[%s] event=%s params=%s", self.serial, ev, msg.get("params"))
            return
        logger.warning("agent[%s] 收到协议外消息: %s", self.serial, msg)

    async def close(self, *, reason: str = "router_close") -> None:
        if self._closed:
            return
        self._closed = True
        # 解挂所有 pending future
        for rpc_id, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_exception(NoAgentError(self.serial))
        self._pending.clear()
        try:
            await self.ws.close()
        except Exception:
            pass
        logger.info("agent[%s] 已关闭: %s", self.serial, reason)


def future_id(future: asyncio.Future, pending: Dict[str, asyncio.Future]) -> Optional[str]:
    for k, v in pending.items():
        if v is future:
            return k
    return None


# ---------------------------------------------------------------------------
# Router 单例
# ---------------------------------------------------------------------------
class AgentRouter:
    """所有活跃 agent 连接的注册表。"""

    def __init__(self) -> None:
        self._conns: Dict[str, AgentConnection] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()  # 仅供 async 侧用

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # ------------------------------------------------------------------
    # serial 规范化：ADB 风格 ``127.0.0.1:5555`` 与 URL-safe ``127.0.0.1_5555``
    # 任意一种都视为同一台设备，避免业务侧关心写法差异。
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_serial(serial: str) -> str:
        return serial.replace(":", "_").strip()

    # ------------------------------------------------------------------
    # 连接生命周期（FastAPI websocket endpoint 调用）
    # ------------------------------------------------------------------
    async def register(self, serial: str, ws: WebSocket) -> AgentConnection:
        serial = self.normalize_serial(serial)
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        conn = AgentConnection(serial, ws, loop)
        async with self._lock:
            old = self._conns.get(serial)
            if old is not None:
                logger.warning("agent[%s] 已有旧连接，将关闭", serial)
                await old.close(reason="superseded")
            self._conns[serial] = conn
        logger.info("agent[%s] 已注册 总在线=%d", serial, len(self._conns))
        return conn

    async def unregister(self, conn: AgentConnection, *, reason: str = "disconnect") -> None:
        async with self._lock:
            cur = self._conns.get(conn.serial)
            if cur is conn:
                self._conns.pop(conn.serial, None)
        await conn.close(reason=reason)
        logger.info("agent[%s] 已注销 总在线=%d (%s)", conn.serial, len(self._conns), reason)

    def get(self, serial: str) -> Optional[AgentConnection]:
        return self._conns.get(self.normalize_serial(serial))

    def list_serials(self) -> list:
        return list(self._conns.keys())

    def snapshot(self) -> list:
        now = time.time()
        return [
            {
                "serial": c.serial,
                "connected_for_s": round(now - c.connected_at, 1),
                "idle_for_s": round(now - c.last_seen_at, 1),
                "pending_rpc": len(c._pending),
            }
            for c in self._conns.values()
        ]

    # ------------------------------------------------------------------
    # 业务侧入口（同步线程调用）
    # ------------------------------------------------------------------
    def call_sync(
        self,
        serial: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Any:
        """业务线程同步调用。内部走 run_coroutine_threadsafe 桥到事件循环。"""
        key = self.normalize_serial(serial)
        conn = self._conns.get(key)
        if conn is None:
            raise NoAgentError(serial)
        loop = self._loop
        if loop is None or not loop.is_running():
            raise RuntimeError("AgentRouter 事件循环未就绪")
        coro = conn.call(method, params, timeout=timeout)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout + 1.0)


# ---------------------------------------------------------------------------
# 全局单例（供 server.py / agent_driver.py 共用）
# ---------------------------------------------------------------------------
_GLOBAL: Optional[AgentRouter] = None


def get_router() -> AgentRouter:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = AgentRouter()
    return _GLOBAL


# ---------------------------------------------------------------------------
# FastAPI 路由挂载
# ---------------------------------------------------------------------------
def mount_agent_routes(app: FastAPI, router: Optional[AgentRouter] = None) -> AgentRouter:
    router = router or get_router()

    @app.on_event("startup")
    async def _bind_loop():
        router.bind_loop(asyncio.get_event_loop())

    @app.websocket("/agent/{serial}")
    async def _agent_ws(ws: WebSocket, serial: str):
        await ws.accept()
        conn = await router.register(serial, ws)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except Exception:
                    logger.exception("agent[%s] JSON 解析失败: %s", serial, raw[:200])
                    continue
                if not isinstance(msg, dict):
                    logger.warning("agent[%s] 顶层非 object: %s", serial, msg)
                    continue
                try:
                    conn.handle_incoming(msg)
                except Exception:
                    logger.exception("agent[%s] handle_incoming 异常", serial)
        except WebSocketDisconnect as e:
            await router.unregister(conn, reason=f"disconnect code={e.code}")
        except Exception:
            logger.exception("agent[%s] websocket 异常", serial)
            await router.unregister(conn, reason="error")

    @app.get("/api/agents")
    async def _list_agents():
        return {"agents": router.snapshot()}

    return router

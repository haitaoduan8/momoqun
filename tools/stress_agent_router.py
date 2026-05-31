"""Mock Agent 并发压测脚本 — 路线 C Week 3-B。

模拟 N 个 APK Agent 接入 master，再启动 N 个业务线程并发调用
``dump_hierarchy / click``，统计 RPC 延迟分布与吞吐。

示例：

    python tools/stress_agent_router.py --agents 50 --duration 30 \\
        --workers 50 --port 18080

输出（示例）：

    [stress] agents=50 workers=50 duration=30.1s
    [stress] total=3128 ok=3128 fail=0 throughput=104.0 req/s
    [stress] latency_ms: p50=24.1 p95=58.6 p99=121.3 max=215.0
    [stress] ALL OK

依赖：uvicorn + fastapi + websockets。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import statistics
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import uvicorn
import websockets
from fastapi import FastAPI

# 让脚本可作为 python -m 或直接 python tools/... 运行
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from agent_router import get_router, mount_agent_routes  # noqa: E402


# ---------------------------------------------------------------------------
# Mock agent coroutine
# ---------------------------------------------------------------------------
async def _mock_agent(ws_url: str, fake_xml: str) -> None:
    """连上 master，持续应答 RPC。"""
    try:
        async with websockets.connect(ws_url, max_size=2**22, open_timeout=10) as ws:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                method = msg.get("method")
                rpc_id = msg.get("id")
                if method == "dump_hierarchy":
                    result = {"xml": fake_xml}
                elif method == "click":
                    result = {"ok": True}
                elif method == "window_size":
                    result = {"w": 1080, "h": 1920}
                elif method == "ping":
                    result = {"pong": True, "uptime_ms": 1}
                else:
                    await ws.send(json.dumps({
                        "id": rpc_id,
                        "error": {"code": -32601, "message": f"no_such: {method}"},
                    }))
                    continue
                await ws.send(json.dumps({"id": rpc_id, "result": result}))
    except asyncio.CancelledError:
        return
    except Exception as e:
        print(f"[mock_agent] {ws_url} 连接异常: {type(e).__name__}: {e}", file=sys.stderr)


async def _run_mock_agents(ws_base: str, serials: List[str], fake_xml: str,
                           stop_evt: "threading.Event") -> None:
    """同时跑 N 个 agent，直到 stop_evt 被设。"""
    tasks = []
    for sn in serials:
        url = f"{ws_base}/agent/{sn}"
        tasks.append(asyncio.create_task(_mock_agent(url, fake_xml)))

    while not stop_evt.is_set():
        await asyncio.sleep(0.1)
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# Worker：业务线程
# ---------------------------------------------------------------------------
def _worker_loop(serial: str, deadline: float, samples: list, stats: dict) -> None:
    """对一个 serial 反复发 dump_hierarchy + click，记录每次延迟。"""
    router = get_router()
    while time.time() < deadline:
        # dump
        t0 = time.perf_counter()
        try:
            router.call_sync(serial, "dump_hierarchy",
                             {"compressed": True}, timeout=10.0)
            samples.append((time.perf_counter() - t0) * 1000.0)
            stats["ok"] += 1
        except Exception as e:
            samples.append((time.perf_counter() - t0) * 1000.0)
            stats["fail"] += 1
            stats["last_err"] = type(e).__name__

        # click
        t0 = time.perf_counter()
        try:
            router.call_sync(serial, "click",
                             {"x": 540, "y": 960}, timeout=10.0)
            samples.append((time.perf_counter() - t0) * 1000.0)
            stats["ok"] += 1
        except Exception:
            samples.append((time.perf_counter() - t0) * 1000.0)
            stats["fail"] += 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agents", type=int, default=50,
                   help="并发 mock agent 数量 (默认 50)")
    p.add_argument("--workers", type=int, default=None,
                   help="并发业务线程数 (默认与 agents 相同)")
    p.add_argument("--duration", type=float, default=20.0,
                   help="压测持续秒数 (默认 20s)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=18080)
    p.add_argument("--xml-bytes", type=int, default=80_000,
                   help="mock dump_hierarchy 返回的 XML 大小 (默认 80KB)")
    args = p.parse_args()

    agents = args.agents
    workers = args.workers or agents
    duration = args.duration

    serials = [f"stress-{uuid.uuid4().hex[:6]}-{i:03d}" for i in range(agents)]
    fake_xml = "<hierarchy>" + "<node text='x'/>" * (args.xml_bytes // 18) + "</hierarchy>"

    # ---------- 启动 FastAPI app（在专用线程） ----------
    app = FastAPI()
    mount_agent_routes(app)

    ws_base = f"ws://{args.host}:{args.port}"
    cfg = uvicorn.Config(app, host=args.host, port=args.port,
                         log_level="error", lifespan="on")
    server = uvicorn.Server(cfg)
    server_th = threading.Thread(target=server.run, daemon=True)
    server_th.start()
    # 等 server ready
    for _ in range(50):
        if getattr(server, "started", False):
            break
        time.sleep(0.1)
    if not getattr(server, "started", False):
        print("[stress] server 未启动，abort", file=sys.stderr)
        return 1

    # ---------- mock agents 在独立 asyncio 线程里跑 ----------
    agent_loop = asyncio.new_event_loop()
    stop_evt = threading.Event()

    def _agent_thread() -> None:
        asyncio.set_event_loop(agent_loop)
        agent_loop.run_until_complete(
            _run_mock_agents(ws_base, serials, fake_xml, stop_evt)
        )

    th_agent = threading.Thread(target=_agent_thread, daemon=True)
    th_agent.start()

    # 等所有 agent 连上
    router = get_router()
    deadline_connect = time.time() + 15
    while time.time() < deadline_connect:
        if len(router.list_serials()) >= agents:
            break
        time.sleep(0.1)
    online = len(router.list_serials())
    print(f"[stress] agents online={online}/{agents}")
    if online < agents:
        print(f"[stress] WARN 仅 {online} 个 agent 连上", file=sys.stderr)

    # ---------- workers 开跑 ----------
    samples: List[float] = []
    stats = {"ok": 0, "fail": 0, "last_err": ""}
    sample_lock = threading.Lock()

    def _local_samples_then_merge(serial: str, deadline_ts: float):
        local: list = []
        local_stats = {"ok": 0, "fail": 0, "last_err": ""}
        _worker_loop(serial, deadline_ts, local, local_stats)
        with sample_lock:
            samples.extend(local)
            stats["ok"] += local_stats["ok"]
            stats["fail"] += local_stats["fail"]
            if local_stats["last_err"]:
                stats["last_err"] = local_stats["last_err"]

    start_ts = time.perf_counter()
    deadline_ts = time.time() + duration
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = []
        for i in range(workers):
            sn = router.normalize_serial(serials[i % agents])
            futs.append(pool.submit(_local_samples_then_merge, sn, deadline_ts))
        for f in as_completed(futs):
            with contextlib.suppress(Exception):
                f.result()
    elapsed = time.perf_counter() - start_ts

    # ---------- 结束 ----------
    stop_evt.set()
    server.should_exit = True
    time.sleep(0.8)
    try:
        agent_loop.call_soon_threadsafe(agent_loop.stop)
    except Exception:
        pass

    # ---------- 汇总 ----------
    total = stats["ok"] + stats["fail"]
    if total == 0:
        print("[stress] FAIL no requests done", file=sys.stderr)
        return 2

    samples.sort()
    p50 = samples[int(len(samples) * 0.50)]
    p95 = samples[int(len(samples) * 0.95)]
    p99 = samples[int(len(samples) * 0.99)] if len(samples) >= 100 else samples[-1]
    s_max = samples[-1]
    avg = statistics.mean(samples)

    print(f"[stress] agents={agents} workers={workers} duration={elapsed:.1f}s xml={args.xml_bytes}B")
    print(f"[stress] total={total} ok={stats['ok']} fail={stats['fail']} "
          f"throughput={total / elapsed:.1f} req/s")
    print(f"[stress] latency_ms: avg={avg:.1f} p50={p50:.1f} p95={p95:.1f} "
          f"p99={p99:.1f} max={s_max:.1f}")
    if stats["fail"]:
        print(f"[stress] last_err={stats['last_err']}")

    # 简单门槛
    ok = stats["fail"] / total < 0.005 and p95 < 500
    if ok:
        print("[stress] ALL OK")
        return 0
    print("[stress] FAIL (p95 >= 500ms or fail-rate >= 0.5%)", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())

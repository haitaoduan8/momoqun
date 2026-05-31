# momoqun 多模拟器扩容架构 — 路线 C 实施方案

> 目标：单台 Windows 主机（双路 E5-2686 v4 / 96GB RAM）稳定驱动 50–100 台模拟器。
> 路线选择：**轻量 Android APK Agent + Python Master**。

---

## 1. 现状瓶颈

| 层 | 问题 | 影响 |
|----|------|------|
| ADB Server | 单进程串行化所有命令 | >12 台后命令排队 |
| Python GIL | 单进程多线程 CPU 拥塞 | 模板匹配/解析 |
| `data/friends.json` | 全局单文件 + RLock | 多设备写竞争 |
| `data/state.json` | 全局单文件 | 消息池轮次混乱 |
| `subprocess.run(adb …)` | 同步阻塞 | UI 卡顿 |
| Flet UI 轮询 | 1s 刷全部设备 | 100 台时主线程吃满 |

预估当前能稳跑 6–10 台，12–16 临界，>24 崩溃。

---

## 2. 目标架构

```
┌───────────────────────── Windows Host ─────────────────────────┐
│                                                                │
│  ┌─────────────────────┐         ┌──────────────────────────┐  │
│  │  Python Master      │  WS     │  Emulator x N            │  │
│  │  (FastAPI + Flet)   │ <─────> │  ┌────────────────────┐  │  │
│  │                     │ reverse │  │ momoqun-agent.apk  │  │  │
│  │  - server.py        │  RPC    │  │  - Accessibility   │  │  │
│  │  - agent_router.py  │         │  │  - IME             │  │  │
│  │  - device_manager   │         │  │  - WS client       │  │  │
│  │  - core/* (业务)    │         │  └────────────────────┘  │  │
│  │  - drivers/         │         └──────────────────────────┘  │
│  └─────────────────────┘                                       │
│                                                                │
│  data/                                                         │
│    friends/<serial>.json    ← per-device                       │
│    state/<serial>.json      ← per-device                       │
│    archive/friends/<serial>/<ts>.json   ← 安全退出归档         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**关键决策**：完全绕过 ADB Server。Agent APK 上电后主动连 master 的 WS 端口，
master 通过同一条连接下发 JSON-RPC 调用（dump_hierarchy / click / type / swipe），
agent 在 Android 进程内用 AccessibilityService 直接执行，无需 ADB。

---

## 3. 实施节奏（3 周）

### Week 1：Python 基础设施

| Day | Milestone | 验收 |
|-----|-----------|------|
| 1 | per-device storage 拆分 + 安全退出归档清零 | 单设备跑通；多设备启动各自写自己的 json |
| 2 | `core/drivers/base.py` Driver Protocol；现 `core/driver.py` 迁到 `core/drivers/u2_driver.py` | import 不报错，业务模块全部依赖 `Driver` 而非 `u2.Device` |
| 3 | `core/drivers/agent_driver.py` stub（接口齐全） | 接口签名与 `u2_driver` 一致 |
| 4 | `agent_router.py` WebSocket 反向 RPC 骨架（无业务） | 假 agent 连接，能 ping/pong |
| 5 | `docs/agent-protocol.md` 定稿 + 错误码冻结 | 协议字段、版本号、心跳约定全部写死 |

### Week 2：Android Agent APK

| Day | Milestone | 验收 |
|-----|-----------|------|
| 1–2 | `agent-android/` Studio 工程脚手架 + WebSocket client + 心跳 | apk 装到模拟器，能连上 master |
| 3 | AccessibilityService：dump_hierarchy / click / long_click / swipe | master 调 RPC 能拿到 XML / 完成点击 |
| 4 | InputMethodService：type_text（替代 ADB Keyboard） | 中文输入成功率 100% |
| 5 | Foreground service + boot receiver + 自启 | 模拟器开机自动上线 |

### Week 3：联调 / 压测 / 打包

| Day | Milestone | 验收 |
|-----|-----------|------|
| 1 | `agent_driver.py` 接上真实 agent，跑通一台设备完整一轮 | 与 u2 模式行为一致 |
| 2 | `device_manager` 切换到 `AgentDriver`；SSE 替换轮询 | UI 不卡 |
| 3 | 加 `WorkerSupervisor`：心跳 + 单设备熔断 + 自动重连 | 模拟器掉线/重连不影响其他设备 |
| 4 | 20 台 / 50 台 / 100 台逐级压测 | 单轮平均耗时不衰减 >20% |
| 5 | `momoqun.spec` 更新 + agent.apk 嵌入资源 + Windows EXE 打包 | 双击 exe 启动；UI 装 APK 一键完成 |

---

## 4. 关键模块改动清单

### 4.1 已实施（Day 1）

- `data/storage.py`：`StorageHandler(serial=…)` + `archive_and_clear()`
- `core/message_pool.py`：`MessagePoolManager(serial=…)`
- `core/pipeline.py` / `core/chatter.py`：接受 serial
- `device_manager.py`：注入 serial
- `main.py`：单设备走 per-device 路径
- `server.py`：atexit + 信号钩子归档所有活跃设备

### 4.2 待实施

- `core/drivers/base.py`（新）
- `core/drivers/u2_driver.py`（迁移）
- `core/drivers/agent_driver.py`（新）
- `agent_router.py`（新）
- `agent-android/`（新工程）
- `momoqun.spec`（更新 hidden imports + datas）

---

## 5. 协议草稿（Day 5 定稿）

```jsonc
// master → agent
{ "id": "uuid", "method": "click",
  "params": { "x": 100, "y": 200 } }

// agent → master
{ "id": "uuid", "result": { "ok": true } }
{ "id": "uuid", "error": { "code": -32001, "message": "node not visible" } }
```

| method | params | result |
|--------|--------|--------|
| `ping` | `{}` | `{ "pong": true, "uptime": int }` |
| `dump_hierarchy` | `{ "compressed": bool }` | `{ "xml": str }` |
| `click` | `{ "x": int, "y": int }` | `{ "ok": bool }` |
| `long_click` | `{ "x": int, "y": int, "duration_ms": int }` | `{ "ok": bool }` |
| `swipe` | `{ "x1","y1","x2","y2","duration_ms" }` | `{ "ok": bool }` |
| `type_text` | `{ "text": str }` | `{ "ok": bool }` |
| `press_key` | `{ "key": "back/home/enter" }` | `{ "ok": bool }` |
| `screenshot` | `{ "quality": int }` | `{ "png_b64": str }` |
| `wait_for` | `{ "xpath": str, "timeout_ms": int }` | `{ "matched": bool }` |
| `close` | `{}` | `{ "ok": bool }` |

错误码：`-32600` 协议错误；`-32601` 未知方法；`-32001` 元素未找到；`-32002` 操作超时；`-32003` 服务未授权（Accessibility 未启用）。

---

## 6. 风险 & 回退

| 风险 | 缓解 |
|------|------|
| 模拟器 RAM 紧张 | 后期 `simulator-thinning.md`：1 核 800MB 480p，无 GPU |
| Accessibility 误关 | Foreground service 监控 + UI 红点提示 |
| 中文 IME 输入异常 | 保留 ADB Keyboard 兜底（双驱动） |
| 100 台目标不达 | 降级到 80 / 50，CPU/RAM/网络 profile 确认瓶颈 |

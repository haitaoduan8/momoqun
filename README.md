# momoqun

陌陌群控自动化：Master 控制面 + 模拟器 Agent + Web 控制台。

## 架构

```
Web UI (Next.js)  ──HTTP──►  server.py (FastAPI)
                                  │
                    WebSocket ◄───┘
                                  │
                         agent-android (每台模拟器)
                                  │
                         uiautomator2 / 截图 / 点击
```

- **Master**：本仓库 `server.py`，负责设备调度、配置、日志与统计。
- **Agent**：`agent-android/`，在模拟器内连接 Master WebSocket，执行 UI 自动化 RPC。
- **Web UI**：`webui/`，设备面板、配置、账号检测、运行日志。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd webui && npm install && npm run build && cd ..
```

### 2. 启动 Master

```bash
python server.py
```

浏览器打开控制台（默认 `http://127.0.0.1:8765`）。

### 3. 配置 Agent

1. 在 Web UI「Master 地址」复制 `ws://...` 地址。
2. 安装并打开 Android Agent（见 `agent-android/README.md`）。
3. 填入 Master 地址；若启用鉴权，填写相同 API Token。

### 4. 启动设备

在「在线 Agent」列表点击 ▶，或在设备卡片上开始/暂停。

## 配置

主配置文件：`config/settings.yaml`（也可在 Web UI「配置」页编辑，支持热更新）。

| 区块 | 说明 |
|------|------|
| `security.api_token` | 非空启用 HTTP / WebSocket 鉴权 |
| `security.allow_shell_exec` | 是否允许 Agent 反向 `shell_exec`（默认关闭） |
| `security.heartbeat_timeout_sec` | Agent 心跳超时断开（秒） |
| `message_pools` | 多轮聊天话术池 |
| `chat_ignore_names` | 聊天列表忽略的系统会话名 |
| `direct_group_mode` | 直接拉群模式（跳过聊天/关注） |

环境变量：`MOMOQUN_API_TOKEN` 可覆盖 YAML 中的 `api_token`。

## 鉴权

1. 在 `config/settings.yaml` 设置 `security.api_token`，或导出 `MOMOQUN_API_TOKEN`。
2. Web UI 首次访问输入相同令牌（存于浏览器 `localStorage`）。
3. Agent 在应用内填写相同令牌（拼接到 WebSocket URL 的 `?token=`）。

公开端点：`GET /api/auth/status`（无需令牌）。

## 开发与测试

```bash
# Python 单元测试
python -m unittest discover -s tests -p "test_*.py" -v

# Web UI 开发模式（需 Master 已启动或配置 proxy）
cd webui && npm run dev
```

## 打包

```bash
pip install -r requirements-build.txt
pyinstaller momoqun.spec
```

Release CI 见 `.github/workflows/`。

## 文档

- `docs/agent-protocol.md` — Agent WebSocket 协议
- `webui/README.md` — 前端说明
- `agent-android/README.md` — Android Agent 构建

## 目录结构

```
├── server.py           # FastAPI 控制面
├── device_manager.py   # 多设备调度
├── agent_router.py     # Agent WebSocket 路由
├── auth.py             # API / WS 鉴权
├── core/               # 自动化流水线（招呼、聊天、拉群等）
├── config/             # settings.yaml、UI 元素定位
├── webui/              # Next.js 控制台
├── agent-android/      # 模拟器 Agent APK
└── tests/              # 单元测试
```

# 路线 C 部署运维手册 (Master + APK Agent)

> 适用：单台 Windows + 50~100 个模拟器，APK Agent 反向 WebSocket。
> 协议规范见 [`agent-protocol.md`](./agent-protocol.md)。
> 计划详情见 [`../MULTI_DEVICE_PLAN.md`](../MULTI_DEVICE_PLAN.md)。

---

## 1. 物料清单（部署前确认）

| 物料 | 位置 | 用途 |
|------|------|------|
| `momoqun.exe` + `dist/momoqun/` | EXE 包根目录 | Master 主程序 |
| `agent-bundle/app-release.apk` | EXE 包内 / Android Studio 产出 | 每台模拟器跑的 Agent |
| `agent-bundle/agent-protocol.md` | EXE 包内 | 协议规范（排查协议错误时用） |
| `agent-bundle/tools/stress_agent_router.py` | EXE 包内 | 现场压测 |
| `scripts/deploy_agent.ps1` / `.sh` | 仓库根 | adb 批量推送 + 配置 |
| `scripts/setup_permissions.ps1` / `.sh` | 仓库根 | adb 一键开 Accessibility/IME（root 模拟器） |

---

## 2. Windows 上构建 master EXE

```powershell
# 1) 准备环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-build.txt

# 2) 在 Windows 上构建（不能在 Mac 上交叉编译）
pyinstaller momoqun.spec

# 3) 产物
#   dist\momoqun\momoqun.exe                       Master 主程序
#   dist\momoqun\agent-bundle\app-release.apk      Agent APK（仅当 step 3 完成后存在）
#   dist\momoqun\agent-bundle\agent-protocol.md    协议
#   dist\momoqun\agent-bundle\tools\stress_*.py    压测脚本
```

## 3. 构建 Agent APK

在 Windows / macOS 任意一台带 **Android Studio Iguana (2023.2.1+)** 的开发机上：

```bash
# 1) 用 Android Studio 打开 agent-android/ 目录
# 2) Gradle Sync 自动完成（首次 3-5 分钟）
# 3) 顶部菜单 → Build → Build APK(s)
# 4) 产物：
#     agent-android/app/build/outputs/apk/debug/app-debug.apk        (开发用)
#     agent-android/app/build/outputs/apk/release/app-release.apk    (生产用 / 推荐)
```

> 把 APK 拷贝到 `dist/momoqun/agent-bundle/` 下，下次 `pyinstaller momoqun.spec`
> 自动包含；也可直接拷贝到运维机的 `agent-bundle/` 给 deploy 脚本用。

## 4. Master 启动

### 4.1 Windows 防火墙

放行 `momoqun.exe` 的入站规则（默认监听 `0.0.0.0:5100`，可在 `config/settings.yaml`
里改）。简单做法：

```powershell
New-NetFirewallRule -DisplayName "momoqun-master" `
    -Direction Inbound -Action Allow `
    -Program "C:\path\to\dist\momoqun\momoqun.exe" `
    -Profile Any
```

或者按端口放行（如果 master 不需要被外网 access，仅限内网 LAN）：

```powershell
New-NetFirewallRule -DisplayName "momoqun-master-5100" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5100 `
    -RemoteAddress LocalSubnet
```

### 4.2 启动 Master

直接双击 `momoqun.exe`，或 cmd：

```cmd
cd C:\path\to\dist\momoqun
momoqun.exe
```

打开浏览器看 `http://localhost:5100` 验证 UI 起来了。

### 4.3 健康检查

```powershell
curl http://localhost:5100/api/agents
# 期望：{"agents":[]} —— 此时还没 Agent 连进来
```

## 5. Agent 部署到模拟器

### 5.1 确认 ADB 连通

```powershell
adb devices
# List of devices attached
# 127.0.0.1:5555    device
# 127.0.0.1:5557    device
# ...
```

如果某台模拟器是 offline / unauthorized：先在模拟器界面里授权或重启 adbd。

### 5.2 批量部署（一条命令搞定）

> 在 **master 机器**或任何能 `adb` 触达模拟器的机器上跑：

```powershell
# Windows
.\scripts\deploy_agent.ps1 `
    -ApkPath ".\agent-bundle\app-release.apk" `
    -MasterUrl "ws://192.168.1.50:5100"
```

```bash
# macOS / Linux
./scripts/deploy_agent.sh -m ws://192.168.1.50:5100 -a ./agent-bundle/app-release.apk
```

脚本会自动：

1. 遍历所有 `adb devices` 中状态为 `device` 的 serial；
2. `adb install -r -g` 装 APK；
3. `adb shell am broadcast -a com.momoqun.agent.SET_CONFIG ...`
   推 master 地址 + serial（serial 自动把 `:` 换成 `_`）；
4. ConfigReceiver 写完配置后自启 ForegroundService 并连 master。

### 5.3 开启 Accessibility + IME（关键）

每台 Agent 必须有：① 启用 `MomoQun Agent` 无障碍 ② 默认输入法 = `MomoQun IME`。

#### 5.3.1 Root 模拟器（雷电 / mumu / 夜神 / BlueStacks）

```powershell
# Windows
.\scripts\setup_permissions.ps1
```

```bash
# macOS / Linux
./scripts/setup_permissions.sh
```

#### 5.3.2 非 root 真机

在每台设备里手动：

1. 打开 **MomoQun Agent** 应用 → 点 **打开无障碍设置** → 启用「MomoQun Agent」；
2. 点 **打开输入法设置** → 启用并切换默认为「MomoQun IME」。

### 5.4 验证 Agent 在线

```powershell
curl http://localhost:5100/api/agents
```

期望看到所有 serial：

```json
{
    "agents": [
        {"serial": "127.0.0.1_5555", "connected_for_s": 8.4, "idle_for_s": 0.1, "pending_rpc": 0},
        {"serial": "127.0.0.1_5557", "connected_for_s": 8.4, "idle_for_s": 0.2, "pending_rpc": 0}
    ]
}
```

## 6. 业务跑起来

打开 master UI（`http://localhost:5100`），在「设备列表」里点 **全部启动**。

DeviceThread 会**自动**走 agent-first 策略：

- 检测到 `agent_router.get(serial)` 命中 → 走 `AgentHandler`（路线 C 高速通路）；
- 否则回退 `uiautomator2.connect(serial)`（ADB 通路，兼容老部署）。

## 7. 现场压测（可选）

部署完先压一遍，验证 master + agent 整链路：

```powershell
cd dist\momoqun\agent-bundle\tools
python stress_agent_router.py --agents 50 --workers 50 --duration 30
```

期望（实测基准）：

| 设备数 | 吞吐 | p50 | p95 | p99 |
|--------|------|-----|-----|-----|
| 50     | ~4000 RPC/s | 12 ms | 15 ms | 16 ms |
| 100    | ~3900 RPC/s | 26 ms | 32 ms | 33 ms |

> 注：该数字是 mock agent（无 emulator）在 macOS arm64 上的基准，
> Windows + 真实模拟器会因 Accessibility dump 耗时上升，
> 但通常 p95 仍能保持在 100 ms 以内。

## 8. 故障排查

| 症状 | 排查 |
|------|------|
| `curl /api/agents` 返回空 | ① 防火墙是否放行 5100；② Agent 通知里 status 是 `connecting` / `failure`？③ APK 内 master_url 是否写错； ④ `adb shell logcat -s MQAgent.WS:*` 看 WS error |
| 业务说 `agent for serial ... not connected` | serial 不匹配：master 拿 ADB serial（`127.0.0.1:5555`），但 Agent 注册用 `127.0.0.1_5555`。router 已自动 normalize（`:` ↔ `_`），如仍报错请用 `/api/agents` 比对实际 serial 拼写 |
| `dump_hierarchy` 返回空 | Accessibility 未启用 / 被系统回收，运行 `setup_permissions` 重新启用 |
| `type_text` 返 `-32003 momoqun-ime not selected` | 默认 IME 不是 momoqun-ime，运行 `setup_permissions` 重新设置 |
| 业务跑得慢 | 看 `/api/agents` 的 `idle_for_s`：> 30s 表示 Agent 心跳异常；`pending_rpc` 长期 > 5 表示业务侧调用速率超过 Agent 处理能力 |
| Agent 频繁掉线 | 通常是模拟器 ROM 杀后台；MainActivity 里的「启动 Agent」可改为开机自启（已实现 `BootReceiver`） |

## 9. 升级流程

```powershell
# 1. master 端
#    停止旧 master.exe
#    覆盖 dist\momoqun\
#    启动新 master.exe

# 2. agent 端
.\scripts\deploy_agent.ps1 -MasterUrl ws://192.168.1.50:5100
# install -r 会保留 SharedPreferences，配置不丢；
# 新 APK 启动后自动重连 master。
```

> 协议向后兼容：master `v1.x` 与 agent `v1.x` 任意版本组合可互通；
> 字段只增不减，新方法 master 单边添加不影响 agent。

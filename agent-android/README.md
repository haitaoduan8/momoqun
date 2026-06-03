# momoqun-agent (Android)

路线 C 的 **设备侧 APK**。每个模拟器跑一份，与 Windows 上的 Python Master 走
反向 WebSocket（emulator → master）。设备需 **root**（`su -c`）；运行时 **不依赖**
master 的 adb `shell_exec`（`security.allow_shell_exec` 可保持 `false`）。

> 协议：见仓库根目录 [`docs/agent-protocol.md`](../docs/agent-protocol.md)（v1.0)。

## 1. 工程结构

```
agent-android/
├── settings.gradle.kts
├── build.gradle.kts
└── app/
    └── src/main/java/com/momoqun/agent/
        ├── service/
        │   ├── AgentForegroundService.kt     # WS 容器 + 通知
        │   ├── MomoQunIME.kt                 # type_text 注入
        │   └── BootReceiver.kt
        ├── ws/
        │   ├── WsClient.kt                   # OkHttp WS + 心跳 + 重连
        │   └── RpcDispatcher.kt
        ├── rpc/
        │   ├── DumpHierarchyHandler.kt       # 本地 su -c app_process dumper
        │   ├── ClickHandler.kt / SwipeHandler.kt / …  # 本地 su -c input
        │   └── …
        ├── dumper/
        │   └── Main.kt                       # shell 侧迭代 UiAutomation dumper
        └── util/
            ├── ShellHelper.kt                # su -c 统一入口
            └── HierarchyXml.kt               # 迭代序列化 → 标准 XML
```

## 2. 构建

1. Android Studio 打开 `agent-android/`。
2. `Build → Build APK(s)` → `app/build/outputs/apk/release/app-release.apk`。

## 3. 部署到模拟器

```powershell
adb -s 127.0.0.1:5555 install -r app-release.apk
```

在模拟器里：

1. 确认 **root** 可用：`adb shell su -c id` → `uid=0(root)`。
2. 打开 **MomoQun Agent**，填 `ws://<宿主机IP>:5100` 与 serial（冒号改下划线，如 `127.0.0.1_5555`）。
3. **打开输入法设置**，默认输入法设为「MomoQun IME」（中文输入需要）。
4. 点 **启动 Agent**，状态为 `connected`。

## 4. dump_hierarchy 路径

```
master --WS--> agent DumpHierarchyHandler
                  --> ShellHelper su -c "pm path …"
                  --> ShellHelper su -c "CLASSPATH=base.apk app_process … dumper.Main"
                  --> stdout XML --WS--> master
```

- 不使用无障碍 `AccessibilityService`。
- 不使用 master `shell_exec` / `uiautomator dump`。
- 深层 UI 树用 [HierarchyXml](app/src/main/java/com/momoqun/agent/util/HierarchyXml.kt) 显式栈迭代，避免平台递归栈溢出。

## 5. master 自检

```bash
curl http://localhost:5100/api/agents
```

## 6. FAQ

**Q: 必须开无障碍吗？**
A: 不需要。点击/滑动/按键/dump 均走本地 `su -c`。

**Q: master 要为每台开 adb 吗？**
A: 业务运行期不需要（仅 WebSocket）。批量装 APK、排障时仍可能用 adb。

**Q: `allow_shell_exec` 要开吗？**
A: 不需要。Agent 已不再调用反向 `shell_exec`。

# momoqun-agent (Android)

路线 C 的 **设备侧 APK**。每个模拟器跑一份，与 Windows 上的 Python Master 走
反向 WebSocket（emulator → master），bypass ADB / uiautomator2 / atx-agent。

> 协议：见仓库根目录 [`docs/agent-protocol.md`](../docs/agent-protocol.md)（v1.0）。

## 1. 工程结构

```
agent-android/
├── settings.gradle.kts            # 单 module，rootProject.name="momoqun-agent"
├── build.gradle.kts               # AGP 8.5.2 + Kotlin 1.9.24
├── gradle.properties              # androidx + non-transitive R
├── gradle/wrapper/...             # 让 Android Studio 帮你 sync 即可
└── app/
    ├── build.gradle.kts           # com.momoqun.agent / minSdk 26 / targetSdk 34
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml
        ├── res/
        │   ├── xml/accessibility_service_config.xml
        │   ├── xml/ime_method.xml
        │   ├── values/strings.xml
        │   ├── values/themes.xml
        │   ├── layout/activity_main.xml
        │   ├── drawable/ic_launcher_*.xml
        │   └── mipmap-anydpi-v26/ic_launcher*.xml
        └── java/com/momoqun/agent/
            ├── AgentApp.kt                       # Application + 通知 channel
            ├── AgentConfig.kt                    # master_url + serial 持久化
            ├── MainActivity.kt                   # 配置 / 启停 / 状态
            ├── service/
            │   ├── AgentForegroundService.kt     # WS 容器 + 通知
            │   ├── A11yService.kt                # rootInActiveWindow / gesture / screenshot
            │   ├── MomoQunIME.kt                 # type_text 注入
            │   └── BootReceiver.kt               # 开机自启
            ├── ws/
            │   ├── WsClient.kt                   # OkHttp WS + 心跳 + 指数退避重连
            │   └── RpcDispatcher.kt              # method → handler
            ├── rpc/
            │   ├── DumpHierarchyHandler.kt
            │   ├── ClickHandler.kt
            │   ├── LongClickHandler.kt
            │   ├── SwipeHandler.kt
            │   ├── PressKeyHandler.kt
            │   ├── TypeTextHandler.kt
            │   ├── WindowSizeHandler.kt
            │   ├── ScreenshotHandler.kt
            │   ├── ImeStatusHandler.kt
            │   └── KeyboardVisibleHandler.kt
            └── util/
                └── HierarchyXml.kt               # AccessibilityNodeInfo → uiautomator2 兼容 XML
```

## 2. 构建（在 Windows / macOS 上都行）

1. 装 **Android Studio Iguana (2023.2.1)** 或更新，里面带 AGP 8.5+ / Gradle 8.7。
2. `File → Open → 选择 agent-android/` 目录。
3. Studio 会自动下 Gradle wrapper 与 dependencies。第一次同步 3–5 分钟。
4. 顶部菜单 `Build → Make Project` 或直接 `Build → Build APK(s)`。
5. APK 产物：`agent-android/app/build/outputs/apk/debug/app-debug.apk`。

> 如果 Studio 提示缺少 `gradle-wrapper.jar`：菜单 `Help → Show Log in Explorer`
> → 切到工程根 → 终端执行 `gradle wrapper`（或让 Studio 自己补齐）。本仓库
> 只提交了 `gradle-wrapper.properties`，JAR 让 Studio 自动生成（避免二进制入库）。

## 3. 部署到模拟器

每个模拟器（雷电 / mumu / 夜神 / BlueStacks 等）跑一份 agent。

```powershell
# 假设 adb 在 PATH
adb -s 127.0.0.1:5555 install -r app-debug.apk
```

然后在该模拟器里：

1. 打开 **MomoQun Agent**。
2. 在「Master 地址」填 `ws://<windows_host_ip>:5100`（在 Windows 上跑 master 的 IP）。
   - 模拟器内访问宿主机：雷电/夜神/mumu 默认是宿主机 IP；
   - Android Studio AVD 用 `10.0.2.2`（虚拟网关）。
3. 在「Serial」填这个模拟器的 ADB 序列号（如 `127.0.0.1_5555`，**冒号要替换成下划线**）。
   - 这个 serial 同时决定 master 上 `data/friends/<serial>.json` 等文件的命名。
4. 点 **打开无障碍设置**，启用「MomoQun Agent」。
5. 点 **打开输入法设置**，把「MomoQun IME」设为默认输入法。
6. 回 App，点 **启动 Agent**。状态条变成 `connected` 即可。

## 4. master 侧自检

Windows 上 master 跑起来后：

```bash
curl http://localhost:5100/api/agents
# => {"agents":[{"serial":"127.0.0.1_5555","connected_for_s":12.3, ...}]}
```

Master 业务侧（`core/drivers/agent_driver.AgentHandler`）会通过这个连接派发
`dump_hierarchy / click / swipe / type_text / screenshot` 等方法。

## 5. 性能预算

- WS 帧 ≤ 200 KB（dump_hierarchy 在中等 UI 复杂度下约 80–150 KB），master 端 200 设备并发处理 ≈ 30 MB/s。
- `dump_hierarchy` 不再走 atx-agent，单次耗时 30–80 ms（比 u2 的 200–400 ms 快 5–10×）。
- 心跳 10s 一次，相比 atx-agent 的 ping 风暴减少 99% 流量。

## 6. FAQ

**Q: minSdk 26 / API 8.0+ 够用吗？**
A: 主流模拟器都是 Android 9~13。`takeScreenshot()` 要 API 30+，没有的话
`screenshot` RPC 返回 `-32603`，业务侧会自动降级到截屏 fallback（如 ADB
`screencap`）。

**Q: AccessibilityNodeInfo 不带元素的 `index` / `selected` / `password`，导致 uiautomator2 XPath 失效怎么办？**
A: `util/HierarchyXml.kt` 已对齐 uiautomator2 的字段集；如果业务 XPath 用到
我们未输出的字段，提 issue 后追加即可（v1 协议允许在 `result` 里追加字段，
不算 break）。

**Q: 通知能不能去掉？**
A: 前台 Service 必须有通知；可以把 channel importance 设为 `IMPORTANCE_MIN`
进一步降权，或在用户隐私设置里隐藏。

## 7. 后续

- Week 3 集成阶段：在 `device_manager.py` 里加一个 "agent-first" 选择策略：
  优先检查 `agent_router.list_connected()`，命中走 `AgentHandler`，未命中
  回退到 `uiautomator2 DeviceHandler`，业务模块全程不感知。
- 压测目标：单台 Windows + 32C/64T + 96GB → 50 emulator 长时间稳定（业务循环 < 5% 失败率）。

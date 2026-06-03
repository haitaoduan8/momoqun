# Keep IME / foreground service classes referenced from AndroidManifest only
-keep class com.momoqun.agent.service.MomoQunIME { *; }
-keep class com.momoqun.agent.service.AgentForegroundService { *; }
-keep class com.momoqun.agent.service.BootReceiver { *; }

# Shell 侧 dumper：仅由 master 经 app_process 反射式调用，代码内无引用，
# 必须 keep 否则开启 minify 后会被裁剪/改名导致 app_process 找不到入口。
-keep class com.momoqun.agent.dumper.Main { *; }

# OkHttp keeps own ProGuard rules; nothing extra needed here.

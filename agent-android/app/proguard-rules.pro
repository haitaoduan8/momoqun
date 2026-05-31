# Keep accessibility/IME service classes referenced from AndroidManifest only
-keep class com.momoqun.agent.service.A11yService { *; }
-keep class com.momoqun.agent.service.MomoQunIME { *; }
-keep class com.momoqun.agent.service.AgentForegroundService { *; }
-keep class com.momoqun.agent.service.BootReceiver { *; }

# OkHttp keeps own ProGuard rules; nothing extra needed here.

package com.momoqun.agent.dumper

import android.app.UiAutomation
import android.graphics.Point
import android.os.HandlerThread
import android.os.Looper
import android.view.Display
import android.view.accessibility.AccessibilityNodeInfo
import com.momoqun.agent.util.HierarchyXml

/**
 * 独立 dumper 入口,**不在 APK 主进程内运行**:由 Agent 经本地 `su -c` 启动:
 *   `CLASSPATH=<已安装的 base.apk> app_process /system/bin com.momoqun.agent.dumper.Main`
 * 以 **shell/root** 身份运行,XML 经 stdout 返回后由 WebSocket 传给 master。
 *
 * 目的:在「不开启无障碍、不依赖 master adb」的前提下拿到 UI 树,
 * 且避开平台 `uiautomator dump` 在深层 UI 树上递归序列化导致的栈溢出崩溃。
 *
 * 取树通道与 `uiautomator dump` 相同(shell 侧 `UiAutomation`),
 * 序列化改用 [HierarchyXml] 的显式栈迭代实现。
 *
 * 约定:成功时把 XML 打到 stdout 并以退出码 0 结束;失败时退出码非 0、诊断走 stderr。
 */
object Main {

    @JvmStatic
    fun main(args: Array<String>) {
        // Android 9+(targetSdk 28+)默认拦截隐藏 API。app_process 以 shell 身份运行时
        // 通常豁免,这里再显式放开一次作为保险(失败也无妨)。
        relaxHiddenApi()

        val ht = HandlerThread("mq-dumper")
        ht.start()
        val looper = ht.looper

        var exitCode = 1
        var ua: UiAutomation? = null
        try {
            ua = createAndConnect(looper)

            // 连接后 root 可能短暂为 null(Activity 切换瞬间),重试几次。
            var root: AccessibilityNodeInfo? = null
            for (i in 0 until 12) {
                root = ua.rootInActiveWindow
                if (root != null) break
                Thread.sleep(60)
            }
            if (root == null) {
                System.err.println("mq-dumper: rootInActiveWindow == null")
                exitCode = 2
            } else {
                val (w, h, rotation) = displayMetrics()
                val xml = try {
                    HierarchyXml.serialize(root, w, h, rotation)
                } finally {
                    try { root.recycle() } catch (_: Throwable) {}
                }
                // 只把 XML 写到 stdout,确保 master 端 output 干净可解析。
                System.out.print(xml)
                System.out.flush()
                exitCode = 0
            }
        } catch (t: Throwable) {
            System.err.println("mq-dumper: failed: ${t.javaClass.simpleName}: ${t.message}")
            exitCode = 1
        } finally {
            try {
                val dm = UiAutomation::class.java.getDeclaredMethod("disconnect")
                dm.isAccessible = true
                dm.invoke(ua)
            } catch (_: Throwable) {}
            try { ht.quitSafely() } catch (_: Throwable) {}
        }

        // 用 halt 直接退出:避免非 daemon 线程(HandlerThread/binder)阻塞进程返回,
        // 同时确保把上面确定的退出码交给 master。
        try { System.out.flush() } catch (_: Throwable) {}
        try { System.err.flush() } catch (_: Throwable) {}
        Runtime.getRuntime().halt(exitCode)
    }

    /** 反射构造 `UiAutomation(Looper, IUiAutomationConnection)` 并 connect。shell 身份下放行。 */
    private fun createAndConnect(looper: Looper): UiAutomation {
        val connClass = Class.forName("android.app.UiAutomationConnection")
        val conn = connClass.getDeclaredConstructor().newInstance()
        val iConnClass = Class.forName("android.app.IUiAutomationConnection")

        val ctor = UiAutomation::class.java.getDeclaredConstructor(Looper::class.java, iConnClass)
        ctor.isAccessible = true
        val ua = ctor.newInstance(looper, conn) as UiAutomation

        // 优先 connect(int flags),不存在则退回无参 connect()。
        try {
            val m = UiAutomation::class.java.getDeclaredMethod("connect", Int::class.javaPrimitiveType)
            m.isAccessible = true
            m.invoke(ua, 0)
        } catch (_: NoSuchMethodException) {
            val m = UiAutomation::class.java.getDeclaredMethod("connect")
            m.isAccessible = true
            m.invoke(ua)
        }
        return ua
    }

    /** 不依赖 Context 拿主显示器尺寸与旋转(app_process 里没有 Activity/WindowManager)。 */
    private fun displayMetrics(): Triple<Int, Int, Int> {
        return try {
            val dmgClass = Class.forName("android.hardware.display.DisplayManagerGlobal")
            val instance = dmgClass.getMethod("getInstance").invoke(null)
            val display = dmgClass
                .getMethod("getRealDisplay", Int::class.javaPrimitiveType)
                .invoke(instance, Display.DEFAULT_DISPLAY) as Display
            val p = Point()
            @Suppress("DEPRECATION")
            display.getRealSize(p)
            Triple(p.x, p.y, display.rotation)
        } catch (_: Throwable) {
            // 拿不到就给个不裁剪 bounds 的大值,保证 dump 仍可用。
            Triple(Int.MAX_VALUE, Int.MAX_VALUE, 0)
        }
    }

    private fun relaxHiddenApi() {
        try {
            val vmRuntimeClass = Class.forName("dalvik.system.VMRuntime")
            val runtime = vmRuntimeClass.getDeclaredMethod("getRuntime").invoke(null)
            val setExemptions = vmRuntimeClass.getDeclaredMethod(
                "setHiddenApiExemptions",
                Array<String>::class.java,
            )
            setExemptions.invoke(runtime, arrayOf("L"))
        } catch (_: Throwable) {
            // 老系统无此 API 或已豁免,忽略。
        }
    }
}

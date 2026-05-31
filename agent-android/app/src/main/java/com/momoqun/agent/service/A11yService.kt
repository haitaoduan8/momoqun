package com.momoqun.agent.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.Path
import android.os.Build
import android.util.Log
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import java.util.concurrent.Executors

/**
 * 全局 AccessibilityService：
 * - 维护单例引用供 RPC 调用方拿到 root window node 与 gesture API
 * - 不订阅高频事件（只有 WindowState/Content），减小开销
 *
 * 所有 RPC handler 通过 [INSTANCE] 拿到 service 实例，再调用
 * - [rootInActiveWindow]
 * - [dispatchGesture]
 * - [takeScreenshot]（API 30+）
 */
class A11yService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        INSTANCE = this
        Log.i(TAG, "A11yService connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // no-op; 只用作 hierarchy 抓取与 gesture 派发的 holder
    }

    override fun onInterrupt() {
        Log.w(TAG, "A11yService interrupted")
    }

    override fun onDestroy() {
        Log.i(TAG, "A11yService destroyed")
        if (INSTANCE === this) INSTANCE = null
        super.onDestroy()
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        if (INSTANCE === this) INSTANCE = null
        return super.onUnbind(intent)
    }

    /** 派发单点 tap（click / long_click 共用）。*/
    fun tap(x: Float, y: Float, durationMs: Long = 50L): Boolean {
        val path = Path().apply { moveTo(x, y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGesture(gesture, null, null)
    }

    /** 滑动手势。 */
    fun swipeGesture(x1: Float, y1: Float, x2: Float, y2: Float, durationMs: Long): Boolean {
        val path = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGesture(gesture, null, null)
    }

    /** 截屏：API 30+ 走 takeScreenshot；否则返回 null。 */
    fun screenshotPng(quality: Int, onDone: (ByteArray?) -> Unit) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            onDone(null); return
        }
        val executor = Executors.newSingleThreadExecutor()
        try {
            takeScreenshot(
                android.view.Display.DEFAULT_DISPLAY,
                executor,
                object : TakeScreenshotCallback {
                    override fun onSuccess(screenshot: ScreenshotResult) {
                        try {
                            val bmp = Bitmap.wrapHardwareBuffer(screenshot.hardwareBuffer, screenshot.colorSpace)
                                ?.copy(Bitmap.Config.ARGB_8888, false)
                            val bos = java.io.ByteArrayOutputStream()
                            bmp?.compress(Bitmap.CompressFormat.PNG, quality.coerceIn(1, 100), bos)
                            onDone(bos.toByteArray())
                        } catch (t: Throwable) {
                            Log.e(TAG, "screenshot compress fail", t); onDone(null)
                        } finally {
                            try { screenshot.hardwareBuffer.close() } catch (_: Throwable) {}
                        }
                    }
                    override fun onFailure(errorCode: Int) {
                        Log.w(TAG, "screenshot failed code=$errorCode")
                        onDone(null)
                    }
                },
            )
        } catch (t: Throwable) {
            Log.e(TAG, "screenshot dispatch fail", t)
            onDone(null)
        }
    }

    /** 当前焦点 root，可能为 null（如系统切换 Activity 的瞬间）。 */
    fun activeRoot(): AccessibilityNodeInfo? = rootInActiveWindow

    /** 窗口尺寸：用 WindowManager 拿当前 display 大小（agent 单 display）。 */
    fun displaySize(): Pair<Int, Int> {
        val wm = getSystemService(WINDOW_SERVICE) as WindowManager
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val bounds = wm.currentWindowMetrics.bounds
            bounds.width() to bounds.height()
        } else {
            @Suppress("DEPRECATION")
            val display = wm.defaultDisplay
            val p = android.graphics.Point()
            @Suppress("DEPRECATION")
            display.getRealSize(p)
            p.x to p.y
        }
    }

    companion object {
        private const val TAG = "MQAgent.A11y"

        @Volatile var INSTANCE: A11yService? = null
            private set
    }
}

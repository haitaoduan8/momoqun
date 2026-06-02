package com.momoqun.agent.rpc

import android.util.Log
import com.momoqun.agent.service.A11yService
import com.momoqun.agent.util.HierarchyXml
import com.momoqun.agent.ws.RpcError
import com.momoqun.agent.ws.WsClient
import kotlinx.coroutines.runBlocking
import org.json.JSONObject

object DumpHierarchyHandler {
    private const val TAG = "MQAgent.Dump"
    private const val TMP_PATH = "/data/local/tmp/_mq_hierarchy.xml"
    private const val PKG = "com.momoqun.agent"
    private const val DUMPER_MAIN = "com.momoqun.agent.dumper.Main"

    /** 已安装 base.apk 路径,首次解析后缓存(供 app_process CLASSPATH 用)。 */
    @Volatile
    private var cachedApkPath: String? = null

    fun handle(params: JSONObject): JSONObject {
        // 优先：A11yService（零开销，直接读 AccessibilityNodeInfo 树）
        val a11yXml = tryA11yDump()
        if (a11yXml != null) return JSONObject().put("xml", a11yXml)

        // 回退：请求 master 通过 adb shell 执行 dump（运行在 shell 用户上下文，
        // 不与 APK 进程冲突）。优先用我们内置的迭代 dumper（不崩），失败再退到
        // 平台 uiautomator dump --compressed。
        val xml = masterShellDump()
            ?: throw RpcError(-32603,
                "hierarchy dump failed: A11y off and master shell_exec failed.")
        return JSONObject().put("xml", xml)
    }

    private fun tryA11yDump(): String? {
        val service = A11yService.INSTANCE ?: return null
        return try {
            val root = service.activeRoot() ?: return null
            val (w, h) = service.displaySize()
            val xml = HierarchyXml.serialize(root, w, h)
            root.recycle()
            Log.d(TAG, "A11y dump OK (${xml.length} chars)")
            xml
        } catch (e: Exception) {
            Log.w(TAG, "A11y dump failed", e)
            null
        }
    }

    /**
     * 通过 master 的 adb 通道执行 dump，读回 XML。运行在 shell 用户上下文，
     * 避开 APK 进程的 UiAutomation 冲突。
     *
     * 主路径：以 shell 身份用 `app_process` 加载已安装 APK 内的迭代 dumper
     * （[DUMPER_MAIN]），不走平台递归序列化，深层 UI 树也不崩。
     * 兜底：平台 `uiautomator dump --compressed`（压缩可缓解大部分溢出，但极端页面仍可能崩）。
     */
    private fun masterShellDump(): String? {
        val client = WsClient.INSTANCE ?: run {
            Log.w(TAG, "WsClient not available for shell_exec")
            return null
        }
        return dumpViaAppProcess(client) ?: dumpViaUiautomator(client)
    }

    /** 主路径：CLASSPATH=base.apk app_process … com.momoqun.agent.dumper.Main */
    private fun dumpViaAppProcess(client: WsClient): String? {
        val apk = resolveApkPath(client) ?: run {
            Log.w(TAG, "resolve apk path failed; skip app_process dumper")
            return null
        }
        return try {
            // 先清理可能残留的 uiautomator dump 进程，避免 UiAutomation 连接被占用。
            // 注意：不能用 pkill -f uiautomator，会误杀 app_process 自身。
            val cmd = "pkill -f 'com.android.commands.uiautomator.Launcher' 2>/dev/null; " +
                "CLASSPATH=$apk app_process /system/bin $DUMPER_MAIN"
            val resp = runBlocking { client.shellExec(cmd, timeoutMs = 20_000L) }
            val code = resp.optInt("code", -1)
            val output = resp.optString("output", "")
            if (code == 0 && output.contains("<hierarchy")) {
                Log.d(TAG, "app_process dump OK (${output.length} chars)")
                output
            } else {
                Log.w(TAG, "app_process dump failed: code=$code out=${output.take(200)}")
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "app_process dump shell_exec failed", e)
            null
        }
    }

    /** 兜底路径：平台 uiautomator dump --compressed。 */
    private fun dumpViaUiautomator(client: WsClient): String? {
        return try {
            val cmd = "pkill -f uiautomator 2>/dev/null; rm -f $TMP_PATH && " +
                "uiautomator dump --compressed $TMP_PATH && cat $TMP_PATH && rm -f $TMP_PATH"
            val resp = runBlocking { client.shellExec(cmd, timeoutMs = 20_000L) }
            val code = resp.optInt("code", -1)
            val output = resp.optString("output", "")
            if (code == 0 && output.contains("<hierarchy")) {
                Log.d(TAG, "uiautomator --compressed dump OK (${output.length} chars)")
                output
            } else {
                Log.w(TAG, "uiautomator dump failed: code=$code out=${output.take(200)}")
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "uiautomator dump shell_exec failed", e)
            null
        }
    }

    /** `pm path com.momoqun.agent` → /data/app/.../base.apk，缓存结果。 */
    private fun resolveApkPath(client: WsClient): String? {
        cachedApkPath?.let { return it }
        return try {
            val resp = runBlocking { client.shellExec("pm path $PKG", timeoutMs = 8_000L) }
            val output = resp.optString("output", "")
            val path = output.lineSequence()
                .map { it.trim() }
                .firstOrNull { it.startsWith("package:") }
                ?.removePrefix("package:")
                ?.trim()
            if (!path.isNullOrEmpty()) {
                cachedApkPath = path
                Log.d(TAG, "resolved apk path: $path")
                path
            } else {
                Log.w(TAG, "pm path returned no package line: ${output.take(200)}")
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "resolve apk path failed", e)
            null
        }
    }
}

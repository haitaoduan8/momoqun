package com.momoqun.agent.rpc

import android.util.Log
import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object DumpHierarchyHandler {
    private const val TAG = "MQAgent.Dump"
    private const val PKG = "com.momoqun.agent"
    private const val DUMPER_MAIN = "com.momoqun.agent.dumper.Main"

    /** 已安装 base.apk 路径,首次解析后缓存(供 app_process CLASSPATH 用)。 */
    @Volatile
    private var cachedApkPath: String? = null

    fun handle(params: JSONObject): JSONObject {
        val xml = localRootDump()
        return JSONObject().put("xml", xml)
    }

    /**
     * 设备本地 root shell：迭代 dumper（app_process + 已安装 APK dex）。
     * 不走无障碍、不走 master adb shell_exec、不走平台 uiautomator dump。
     */
    private fun localRootDump(): String {
        val apk = resolveApkPath()
            ?: throw RpcError(-32603, "hierarchy dump failed: pm path $PKG empty (root/su?)")

        val cmd = "pkill -f uiautomator 2>/dev/null; " +
            "CLASSPATH=$apk app_process /system/bin $DUMPER_MAIN"
        val result = ShellHelper.exec(cmd, timeoutSec = 20)
        if (result.ok && result.output.contains("<hierarchy")) {
            Log.d(TAG, "local root dump OK (${result.output.length} chars)")
            return result.output
        }
        val detail = when {
            result.stderr.contains("timeout") -> "timeout"
            result.code != 0 -> "exit=${result.code} stderr=${result.stderr.take(120)}"
            !result.output.contains("<hierarchy") -> "no hierarchy in output (${result.output.length} chars)"
            else -> "unknown"
        }
        Log.w(TAG, "local root dump failed: $detail")
        throw RpcError(-32603, "hierarchy dump failed: $detail")
    }

    private fun resolveApkPath(): String? {
        cachedApkPath?.let { return it }
        val result = ShellHelper.exec("pm path $PKG", timeoutSec = 8)
        val path = result.output.lineSequence()
            .map { it.trim() }
            .firstOrNull { it.startsWith("package:") }
            ?.removePrefix("package:")
            ?.trim()
        if (!path.isNullOrEmpty()) {
            cachedApkPath = path
            Log.d(TAG, "resolved apk path: $path")
            return path
        }
        Log.w(TAG, "pm path failed: code=${result.code} out=${result.output.take(200)}")
        return null
    }
}

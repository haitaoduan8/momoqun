package com.momoqun.agent.rpc

import android.util.Log
import com.momoqun.agent.ws.RpcError
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
        val xml = rootShellDump()
            ?: throw RpcError(-32603, "hierarchy dump failed")
        return JSONObject().put("xml", xml)
    }

    /**
     * 以 root 身份执行 dump，读回 XML。
     *
     * 主路径：用 `app_process` 加载已安装 APK 内的迭代 dumper（[DUMPER_MAIN]），
     * 不走平台递归序列化，深层 UI 树也不崩。
     * 兜底：平台 `uiautomator dump --compressed`。
     */
    private fun rootShellDump(): String? {
        return dumpViaAppProcess() ?: dumpViaUiautomator()
    }

    /** 主路径：CLASSPATH=base.apk app_process … com.momoqun.agent.dumper.Main */
    private fun dumpViaAppProcess(): String? {
        val apk = resolveApkPath() ?: run {
            Log.w(TAG, "resolve apk path failed; skip app_process dumper")
            return null
        }
        return try {
            val result = ShellViaMaster.exec("CLASSPATH=$apk app_process /system/bin $DUMPER_MAIN", timeoutSec = 20)
            if (result.ok && result.stdout.contains("<hierarchy")) {
                Log.d(TAG, "app_process dump OK (${result.stdout.length} chars)")
                result.stdout
            } else {
                Log.w(TAG, "app_process dump failed: code=${result.code} out=${result.stdout.take(200)}")
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "app_process dump failed", e)
            null
        }
    }

    /** 兜底路径：平台 uiautomator dump --compressed。 */
    private fun dumpViaUiautomator(): String? {
        return try {
            val cmd = "pkill -f uiautomator 2>/dev/null; rm -f $TMP_PATH && " +
                "uiautomator dump --compressed $TMP_PATH && cat $TMP_PATH && rm -f $TMP_PATH"
            val result = ShellViaMaster.exec(cmd, timeoutSec = 20)
            if (result.ok && result.stdout.contains("<hierarchy")) {
                Log.d(TAG, "uiautomator --compressed dump OK (${result.stdout.length} chars)")
                result.stdout
            } else {
                Log.w(TAG, "uiautomator dump failed: code=${result.code} out=${result.stdout.take(200)}")
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "uiautomator dump failed", e)
            null
        }
    }

    /** `pm path com.momoqun.agent` → /data/app/.../base.apk，缓存结果。 */
    private fun resolveApkPath(): String? {
        cachedApkPath?.let { return it }
        return try {
            val result = ShellViaMaster.exec("pm path $PKG", timeoutSec = 8)
            val path = result.stdout.lineSequence()
                .map { it.trim() }
                .firstOrNull { it.startsWith("package:") }
                ?.removePrefix("package:")
                ?.trim()
            if (!path.isNullOrEmpty()) {
                cachedApkPath = path
                Log.d(TAG, "resolved apk path: $path")
                path
            } else {
                Log.w(TAG, "pm path returned no package line: ${result.stdout.take(200)}")
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "resolve apk path failed", e)
            null
        }
    }
}

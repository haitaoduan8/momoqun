package com.momoqun.agent.rpc

import android.util.Log
import com.momoqun.agent.service.A11yService
import com.momoqun.agent.util.HierarchyXml
import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object DumpHierarchyHandler {
    private const val TAG = "MQAgent.Dump"
    private const val TMP_PATH = "/data/local/tmp/_mq_hierarchy.xml"

    fun handle(params: JSONObject): JSONObject {
        // ---- 优先：A11yService（零开销，不触发额外 UiAutomation 连接）----
        val a11yXml = tryA11yDump()
        if (a11yXml != null) return JSONObject().put("xml", a11yXml)

        // ---- 回退：uiautomator dump shell 命令（带重试）----
        // 清理残留文件
        ShellHelper.exec("rm -f $TMP_PATH 2>/dev/null")

        val maxRetries = 3
        for (attempt in 1..maxRetries) {
            // 杀掉残留的 uiautomator 进程避免端口冲突
            if (attempt > 1) {
                ShellHelper.exec("pkill -f 'uiautomator' 2>/dev/null")
                Thread.sleep(300L * attempt)
            }

            val dumpOk = ShellHelper.execOk("uiautomator dump $TMP_PATH")
            if (dumpOk) {
                val result = ShellHelper.exec("cat $TMP_PATH && rm -f $TMP_PATH")
                if (result.code == 0 && result.output.isNotEmpty()) {
                    Log.d(TAG, "uiautomator dump OK (attempt=$attempt)")
                    return JSONObject().put("xml", result.output)
                }
            }

            Log.w(TAG, "uiautomator dump failed attempt=$attempt/$maxRetries")
            if (attempt < maxRetries) {
                Thread.sleep(500L * attempt)
            }
        }

        throw RpcError(-32603, "hierarchy dump failed (A11y=off, uiautomator exhausted)")
    }

    /**
     * 如果 A11yService 已连接（用户自行开启），直接用 AccessibilityNodeInfo
     * 序列化 XML，零 shell 开销、不触发额外 UiAutomation 连接。
     */
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
}

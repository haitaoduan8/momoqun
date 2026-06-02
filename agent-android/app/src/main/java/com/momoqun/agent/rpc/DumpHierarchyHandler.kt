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

    fun handle(params: JSONObject): JSONObject {
        // 优先：A11yService（零开销，直接读 AccessibilityNodeInfo 树）
        val a11yXml = tryA11yDump()
        if (a11yXml != null) return JSONObject().put("xml", a11yXml)

        // 回退：请求 master 通过 adb shell 执行 uiautomator dump
        // APK 进程内执行 uiautomator dump 会与 UiAutomation 连接冲突，
        // master 通过 adb 执行在 shell 用户上下文，无此问题。
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
     * 通过 master 的 adb 通道执行 `uiautomator dump`，读回 XML。
     * 运行在 shell 用户上下文，避开 APK 进程的 UiAutomation 冲突。
     */
    private fun masterShellDump(): String? {
        val client = WsClient.INSTANCE ?: run {
            Log.w(TAG, "WsClient not available for shell_exec")
            return null
        }
        return try {
            val cmd = "rm -f $TMP_PATH && uiautomator dump $TMP_PATH && cat $TMP_PATH && rm -f $TMP_PATH"
            // runBlocking: RPC handler 本身是 suspend fun，但 DumpHierarchyHandler.handle 不是
            val resp = runBlocking { client.shellExec(cmd, timeoutMs = 20_000L) }
            val code = resp.optInt("code", -1)
            val output = resp.optString("output", "")
            if (code == 0 && output.contains("<hierarchy")) {
                Log.d(TAG, "master shell dump OK (${output.length} chars)")
                output
            } else {
                Log.w(TAG, "master shell dump failed: code=$code output=${output.take(200)}")
                null
            }
        } catch (e: Exception) {
            Log.w(TAG, "master shell_exec failed", e)
            null
        }
    }
}

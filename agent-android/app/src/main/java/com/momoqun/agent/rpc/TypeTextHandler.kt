package com.momoqun.agent.rpc

import android.util.Log
import com.momoqun.agent.service.MomoQunIME
import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object TypeTextHandler {
    private const val TAG = "MQAgent.TypeText"

    fun handle(params: JSONObject): JSONObject {
        val text = params.optString("text", "")
        if (text.isEmpty()) throw RpcError(-32602, "text required")

        // 优先走 MomoQunIME（支持中文等任意 Unicode）
        val ime = MomoQunIME.INSTANCE
        if (ime != null) {
            val ok = ime.commitTextToInput(text)
            if (ok) {
                Log.d(TAG, "commitText OK (${text.length} chars)")
                return JSONObject().put("ok", true)
            }
            Log.w(TAG, "commitText failed (no InputConnection?)")
        } else {
            Log.w(TAG, "MomoQunIME INSTANCE null")
        }

        // 非 ASCII 不能走 shell input text
        if (text.any { it.code > 127 }) {
            throw RpcError(
                -32603,
                "MomoQunIME commit failed for non-ASCII; ensure input focused and momoqun-ime selected",
            )
        }

        val escaped = text.replace("'", "'\\''")
        val ok = ShellHelper.execOk("input text '$escaped'")
        if (!ok) throw RpcError(-32603, "text input failed")
        return JSONObject().put("ok", true)
    }
}

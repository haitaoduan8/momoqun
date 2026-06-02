package com.momoqun.agent.rpc

import android.util.Log
import com.momoqun.agent.service.MomoQunIME
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object TypeTextHandler {
    private const val TAG = "MQAgent.TypeText"

    fun handle(params: JSONObject): JSONObject {
        val text = params.optString("text", "")
        if (text.isEmpty()) throw RpcError(-32602, "text required")

        // 优先走 MomoQunIME（支持中文等任意 Unicode）
        val ime = MomoQunIME.INSTANCE
        if (ime != null && ime.isVisible()) {
            val ok = ime.commitTextToInput(text)
            if (ok) {
                Log.d(TAG, "commitText OK (${text.length} chars)")
                return JSONObject().put("ok", true)
            }
            Log.w(TAG, "commitText failed, falling back to input text")
        }

        // 回退：root shell input text（仅支持 ASCII）
        val escaped = text.replace("'", "'\\''")
        val ok = ShellViaMaster.ok("input text '$escaped'")
        if (!ok) throw RpcError(-32603, "text input failed")
        return JSONObject().put("ok", true)
    }
}

package com.momoqun.agent.rpc

import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object TypeTextHandler {
    fun handle(params: JSONObject): JSONObject {
        val text = params.optString("text", "")
        if (text.isEmpty()) throw RpcError(-32602, "text required")
        // 转义单引号，用 shell 的 input text 命令
        val escaped = text.replace("'", "'\\''")
        val ok = ShellHelper.execOk("input text '$escaped'")
        if (!ok) throw RpcError(-32603, "text input failed")
        return JSONObject().put("ok", true)
    }
}

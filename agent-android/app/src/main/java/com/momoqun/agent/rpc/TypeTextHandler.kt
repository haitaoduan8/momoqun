package com.momoqun.agent.rpc

import com.momoqun.agent.service.MomoQunIME
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object TypeTextHandler {
    fun handle(params: JSONObject): JSONObject {
        val text = params.optString("text", "")
        if (text.isEmpty()) throw RpcError(-32602, "text required")
        val ime = MomoQunIME.INSTANCE
            ?: throw RpcError(-32003, "momoqun-ime not selected as default IME")
        val ok = ime.commitTextToInput(text)
        if (!ok) throw RpcError(-32603, "no input focus to receive text")
        return JSONObject().put("ok", true)
    }
}

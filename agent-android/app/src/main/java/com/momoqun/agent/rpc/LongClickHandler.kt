package com.momoqun.agent.rpc

import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object LongClickHandler {
    fun handle(params: JSONObject): JSONObject {
        val x = params.optInt("x", -1)
        val y = params.optInt("y", -1)
        val duration = params.optInt("duration_ms", 600).coerceIn(50, 5_000)
        if (x < 0 || y < 0) throw RpcError(-32602, "x/y required")
        // 长按 = swipe 到同一点，持续时间更长
        val ok = ShellHelper.execOk("input swipe $x $y $x $y $duration")
        if (!ok) throw RpcError(-32603, "long-tap failed")
        return JSONObject().put("ok", true)
    }
}

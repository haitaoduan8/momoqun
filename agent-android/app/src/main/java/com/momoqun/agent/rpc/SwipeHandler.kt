package com.momoqun.agent.rpc

import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object SwipeHandler {
    fun handle(params: JSONObject): JSONObject {
        if (!params.has("x1") || !params.has("y1") ||
            !params.has("x2") || !params.has("y2")) {
            throw RpcError(-32602, "x1/y1/x2/y2 required")
        }
        val duration = params.optInt("duration_ms", 200).coerceIn(50, 5_000)
        val x1 = params.getInt("x1")
        val y1 = params.getInt("y1")
        val x2 = params.getInt("x2")
        val y2 = params.getInt("y2")
        val ok = ShellViaMaster.ok("input swipe $x1 $y1 $x2 $y2 $duration")
        if (!ok) throw RpcError(-32603, "swipe failed")
        return JSONObject().put("ok", true)
    }
}

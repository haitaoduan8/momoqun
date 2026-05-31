package com.momoqun.agent.rpc

import com.momoqun.agent.service.A11yService
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object SwipeHandler {
    fun handle(params: JSONObject): JSONObject {
        if (!params.has("x1") || !params.has("y1") ||
            !params.has("x2") || !params.has("y2")) {
            throw RpcError(-32602, "x1/y1/x2/y2 required")
        }
        val duration = params.optInt("duration_ms", 200).coerceIn(50, 5_000).toLong()
        val svc = A11yService.INSTANCE
            ?: throw RpcError(-32003, "accessibility service not enabled")
        val ok = svc.swipeGesture(
            params.getInt("x1").toFloat(),
            params.getInt("y1").toFloat(),
            params.getInt("x2").toFloat(),
            params.getInt("y2").toFloat(),
            duration,
        )
        if (!ok) throw RpcError(-32603, "swipe dispatch failed")
        return JSONObject().put("ok", true)
    }
}

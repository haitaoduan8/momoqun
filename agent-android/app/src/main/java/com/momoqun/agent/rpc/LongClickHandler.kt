package com.momoqun.agent.rpc

import com.momoqun.agent.service.A11yService
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object LongClickHandler {
    fun handle(params: JSONObject): JSONObject {
        val x = params.optInt("x", -1)
        val y = params.optInt("y", -1)
        val duration = params.optInt("duration_ms", 600).coerceIn(50, 5_000).toLong()
        if (x < 0 || y < 0) throw RpcError(-32602, "x/y required")
        val svc = A11yService.INSTANCE
            ?: throw RpcError(-32003, "accessibility service not enabled")
        val ok = svc.tap(x.toFloat(), y.toFloat(), durationMs = duration)
        if (!ok) throw RpcError(-32603, "long-tap dispatch failed")
        return JSONObject().put("ok", true)
    }
}

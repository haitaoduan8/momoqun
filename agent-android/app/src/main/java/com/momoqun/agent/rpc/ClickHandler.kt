package com.momoqun.agent.rpc

import com.momoqun.agent.service.A11yService
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object ClickHandler {
    fun handle(params: JSONObject): JSONObject {
        val x = params.optInt("x", -1)
        val y = params.optInt("y", -1)
        if (x < 0 || y < 0) throw RpcError(-32602, "x/y required")
        val svc = A11yService.INSTANCE
            ?: throw RpcError(-32003, "accessibility service not enabled")
        val ok = svc.tap(x.toFloat(), y.toFloat(), durationMs = 50L)
        if (!ok) throw RpcError(-32603, "tap dispatch failed")
        return JSONObject().put("ok", true)
    }
}

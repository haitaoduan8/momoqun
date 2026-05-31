package com.momoqun.agent.rpc

import com.momoqun.agent.service.A11yService
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object WindowSizeHandler {
    fun handle(): JSONObject {
        val svc = A11yService.INSTANCE
            ?: throw RpcError(-32003, "accessibility service not enabled")
        val (w, h) = svc.displaySize()
        return JSONObject().put("w", w).put("h", h)
    }
}

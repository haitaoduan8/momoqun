package com.momoqun.agent.rpc

import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object WindowSizeHandler {
    fun handle(): JSONObject {
        val result = ShellViaMaster.exec("wm size")
        if (!result.ok) throw RpcError(-32603, "wm size failed")
        // 解析 "Physical size: 1080x1920"
        val match = Regex("(\\d+)x(\\d+)").find(result.stdout)
            ?: throw RpcError(-32603, "failed to parse wm size: ${result.stdout}")
        val w = match.groupValues[1].toInt()
        val h = match.groupValues[2].toInt()
        return JSONObject().put("w", w).put("h", h)
    }
}

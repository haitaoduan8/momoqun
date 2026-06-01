package com.momoqun.agent.rpc

import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object PressKeyHandler {
    fun handle(params: JSONObject): JSONObject {
        val key = params.optString("key", "")
        val keycode = when (key) {
            "back"   -> "4"
            "home"   -> "3"
            "recent" -> "187"
            "power"  -> "26"
            "enter"  -> "66"
            else -> throw RpcError(-32602, "unknown key '$key'")
        }
        val ok = ShellHelper.execOk("input keyevent $keycode")
        if (!ok) throw RpcError(-32603, "key '$key' dispatch failed")
        return JSONObject().put("ok", true)
    }
}

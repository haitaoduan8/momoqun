package com.momoqun.agent.rpc

import android.accessibilityservice.AccessibilityService
import android.os.Build
import com.momoqun.agent.service.A11yService
import com.momoqun.agent.service.MomoQunIME
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object PressKeyHandler {
    fun handle(params: JSONObject): JSONObject {
        val key = params.optString("key", "")
        val svc = A11yService.INSTANCE
            ?: throw RpcError(-32003, "accessibility service not enabled")
        val ok = when (key) {
            "back" -> svc.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
            "home" -> svc.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
            "recent" -> svc.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS)
            "power" -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    svc.performGlobalAction(AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN)
                } else false
            }
            "enter" -> {
                MomoQunIME.INSTANCE?.commitTextToInput("\n") ?: false
            }
            else -> throw RpcError(-32602, "unknown key '$key'")
        }
        if (!ok) throw RpcError(-32603, "key '$key' dispatch failed")
        return JSONObject().put("ok", true)
    }
}

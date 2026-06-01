package com.momoqun.agent.rpc

import android.content.Context
import org.json.JSONObject

object ImeStatusHandler {
    fun handle(ctx: Context): JSONObject {
        // shell 模式下不需要 IME，始终报告可用
        return JSONObject().put("available", true).put("selected", true)
    }
}

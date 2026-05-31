package com.momoqun.agent.rpc

import com.momoqun.agent.service.MomoQunIME
import org.json.JSONObject

object KeyboardVisibleHandler {
    fun handle(): JSONObject {
        val visible = MomoQunIME.INSTANCE?.isVisible() ?: false
        return JSONObject().put("visible", visible)
    }
}

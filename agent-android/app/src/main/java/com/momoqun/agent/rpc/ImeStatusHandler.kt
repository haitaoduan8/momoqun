package com.momoqun.agent.rpc

import android.content.Context
import android.provider.Settings
import com.momoqun.agent.service.MomoQunIME
import org.json.JSONObject

object ImeStatusHandler {
    private const val IME_ID = "com.momoqun.agent/.service.MomoQunIME"

    fun handle(ctx: Context): JSONObject {
        val available = MomoQunIME.INSTANCE != null
        val default = try {
            Settings.Secure.getString(ctx.contentResolver, Settings.Secure.DEFAULT_INPUT_METHOD)
        } catch (_: Throwable) { null }
        val selected = default == IME_ID
        return JSONObject().put("available", available).put("selected", selected)
    }
}

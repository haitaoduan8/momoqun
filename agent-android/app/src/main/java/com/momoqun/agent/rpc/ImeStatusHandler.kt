package com.momoqun.agent.rpc

import android.content.Context
import android.provider.Settings
import android.view.inputmethod.InputMethodManager
import com.momoqun.agent.service.MomoQunIME
import org.json.JSONObject

object ImeStatusHandler {
    fun handle(ctx: Context): JSONObject {
        val imm = ctx.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        val pkg = ctx.packageName
        val enabled = imm.enabledInputMethodList.any { it.packageName == pkg }
        val defaultIme = Settings.Secure.getString(
            ctx.contentResolver,
            Settings.Secure.DEFAULT_INPUT_METHOD,
        )
        val selected = defaultIme?.contains(pkg) == true
        val ime = MomoQunIME.INSTANCE
        return JSONObject()
            .put("available", enabled)
            .put("selected", selected)
            .put("ime_bound", ime != null)
            .put("ime_visible", ime?.isVisible() == true)
    }
}

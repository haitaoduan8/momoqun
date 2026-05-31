package com.momoqun.agent.rpc

import android.util.Base64
import com.momoqun.agent.service.A11yService
import com.momoqun.agent.ws.RpcError
import kotlinx.coroutines.suspendCancellableCoroutine
import org.json.JSONObject
import kotlin.coroutines.resume

object ScreenshotHandler {
    suspend fun handle(params: JSONObject): JSONObject {
        val quality = params.optInt("quality", 80).coerceIn(1, 100)
        val svc = A11yService.INSTANCE
            ?: throw RpcError(-32003, "accessibility service not enabled")

        val bytes = suspendCancellableCoroutine<ByteArray?> { cont ->
            svc.screenshotPng(quality) { data -> cont.resume(data) }
        } ?: throw RpcError(-32603, "screenshot capture failed (API < 30?)")

        val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
        return JSONObject().put("png_b64", b64)
    }
}

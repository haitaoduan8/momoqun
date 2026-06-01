package com.momoqun.agent.rpc

import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object ScreenshotHandler {
    fun handle(params: JSONObject): JSONObject {
        // screencap 输出 PNG 到 stdout，直接 base64 编码，不写临时文件
        val result = ShellHelper.exec("screencap -p | base64")
        if (result.code != 0 || result.output.isEmpty()) {
            throw RpcError(-32603, "screencap failed")
        }
        return JSONObject().put("png_b64", result.output)
    }
}

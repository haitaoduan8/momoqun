package com.momoqun.agent.rpc

import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

/**
 * 长按后拖拽：在同一 su 会话里连续执行 hold + drag，减少抬手间隙。
 * 用于陌陌底部 Tab 未读红点拖走。
 */
object DragHoldHandler {
    fun handle(params: JSONObject): JSONObject {
        if (!params.has("x") || !params.has("y") ||
            !params.has("x2") || !params.has("y2")) {
            throw RpcError(-32602, "x/y/x2/y2 required")
        }
        val x = params.getInt("x")
        val y = params.getInt("y")
        val x2 = params.getInt("x2")
        val y2 = params.getInt("y2")
        val holdMs = params.optInt("hold_ms", 750).coerceIn(100, 2_500)
        val dragMs = params.optInt("drag_ms", 2_200).coerceIn(200, 5_000)
        val cmd = "input swipe $x $y $x $y $holdMs; input swipe $x $y $x2 $y2 $dragMs"
        val ok = ShellHelper.execOk(cmd)
        if (!ok) throw RpcError(-32603, "drag_hold failed")
        return JSONObject().put("ok", true)
    }
}

package com.momoqun.agent.ws

import android.content.Context
import android.os.SystemClock
import com.momoqun.agent.rpc.ClickHandler
import com.momoqun.agent.rpc.DumpHierarchyHandler
import com.momoqun.agent.rpc.ImeStatusHandler
import com.momoqun.agent.rpc.KeyboardVisibleHandler
import com.momoqun.agent.rpc.LongClickHandler
import com.momoqun.agent.rpc.PressKeyHandler
import com.momoqun.agent.rpc.ScreenshotHandler
import com.momoqun.agent.rpc.SwipeHandler
import com.momoqun.agent.rpc.TypeTextHandler
import com.momoqun.agent.rpc.WindowSizeHandler
import org.json.JSONObject

/**
 * 全部 RPC 方法的路由器。
 *
 * 方法集与 [docs/agent-protocol.md] 保持一致：
 * - ping / dump_hierarchy / click / long_click / swipe / press_key / type_text
 * - window_size / screenshot / ime_status / keyboard_visible
 */
class RpcDispatcher(private val ctx: Context) {

    private val startedAtElapsed = SystemClock.elapsedRealtime()

    suspend fun dispatch(req: JsonRpcRequest): JSONObject {
        return when (req.method) {
            "ping" -> handlePing()
            "dump_hierarchy" -> DumpHierarchyHandler.handle(req.params)
            "click" -> ClickHandler.handle(req.params)
            "long_click" -> LongClickHandler.handle(req.params)
            "swipe" -> SwipeHandler.handle(req.params)
            "press_key" -> PressKeyHandler.handle(req.params)
            "type_text" -> TypeTextHandler.handle(req.params)
            "window_size" -> WindowSizeHandler.handle()
            "screenshot" -> ScreenshotHandler.handle(req.params)
            "ime_status" -> ImeStatusHandler.handle(ctx)
            "keyboard_visible" -> KeyboardVisibleHandler.handle()
            else -> throw RpcError(-32601, "no_such_method: ${req.method}")
        }
    }

    private fun handlePing(): JSONObject {
        val uptime = SystemClock.elapsedRealtime() - startedAtElapsed
        return JSONObject().put("pong", true).put("uptime_ms", uptime)
    }
}

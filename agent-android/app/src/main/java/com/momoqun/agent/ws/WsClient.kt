package com.momoqun.agent.ws

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * WebSocket 客户端，单实例对应一条 `agent → master` 长连接。
 *
 * - 收到 `request`（含 `id`+`method`）即异步调用 [onRequest]，回报 `result/error`；
 * - 心跳 10s/次（事件 `heartbeat`）；
 * - 断开后指数退避重连（1s → 30s 封顶）。
 */
class WsClient(
    private val url: String,
    private val onStatus: (String) -> Unit,
    private val onRequest: suspend (JsonRpcRequest) -> JSONObject,
) {

    private val http = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(15, TimeUnit.SECONDS)
        .build()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val running = AtomicBoolean(false)

    @Volatile private var socket: WebSocket? = null
    @Volatile private var hbJob: Job? = null

    fun start() {
        if (!running.compareAndSet(false, true)) return
        scope.launch { connectLoop() }
    }

    fun shutdown() {
        if (!running.compareAndSet(true, false)) return
        try { socket?.close(1000, "client shutdown") } catch (_: Throwable) {}
        socket = null
        hbJob?.cancel(); hbJob = null
        scope.cancel()
    }

    private suspend fun connectLoop() {
        var backoff = 1000L
        while (running.get() && scope.isActive) {
            onStatus("connecting")
            val ok = connectOnce()
            if (!ok) {
                onStatus("disconnected; retry in ${backoff}ms")
                delay(backoff)
                backoff = (backoff * 2).coerceAtMost(30_000)
            } else {
                backoff = 1000L
            }
        }
    }

    private suspend fun connectOnce(): Boolean {
        val request = Request.Builder().url(url).build()
        var connected = false
        val opened = kotlinx.coroutines.CompletableDeferred<Boolean>()
        val closed = kotlinx.coroutines.CompletableDeferred<Boolean>()

        val listener = object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                socket = webSocket
                connected = true
                onStatus("connected")
                hbJob = scope.launch { heartbeat(webSocket) }
                opened.complete(true)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                scope.launch { handleIncoming(webSocket, text) }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "ws failure: ${t.message}")
                onStatus("failure: ${t.message}")
                if (!opened.isCompleted) opened.complete(false)
                if (!closed.isCompleted) closed.complete(true)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                onStatus("closed: $code $reason")
                if (!closed.isCompleted) closed.complete(true)
            }
        }

        val ws = http.newWebSocket(request, listener)
        opened.await()
        if (!connected) {
            try { ws.cancel() } catch (_: Throwable) {}
            return false
        }
        closed.await()
        socket = null
        hbJob?.cancel(); hbJob = null
        return true
    }

    private suspend fun heartbeat(ws: WebSocket) {
        while (scope.isActive && socket === ws) {
            val frame = JSONObject().apply {
                put("event", "heartbeat")
                put("params", JSONObject().put("ts", System.currentTimeMillis()))
            }
            try { ws.send(frame.toString()) } catch (_: Throwable) { return }
            delay(10_000)
        }
    }

    private suspend fun handleIncoming(ws: WebSocket, text: String) {
        val obj = try { JSONObject(text) } catch (t: Throwable) {
            sendError(ws, null, -32600, "invalid json: ${t.message}")
            return
        }
        if (!obj.has("id") || !obj.has("method")) {
            sendError(ws, obj.optString("id", null), -32600, "missing id/method")
            return
        }
        val req = JsonRpcRequest(
            id = obj.getString("id"),
            method = obj.getString("method"),
            params = obj.optJSONObject("params") ?: JSONObject(),
        )
        val reply = try {
            val result = onRequest(req)
            JSONObject().put("id", req.id).put("result", result)
        } catch (e: RpcError) {
            errorObj(req.id, e.code, e.message ?: "rpc error", e.data)
        } catch (t: Throwable) {
            Log.e(TAG, "handler crashed for ${req.method}", t)
            errorObj(req.id, -32603, "internal: ${t.message}", null)
        }
        try { ws.send(reply.toString()) } catch (_: Throwable) {}
    }

    private fun sendError(ws: WebSocket, id: String?, code: Int, msg: String) {
        val e = errorObj(id, code, msg, null)
        try { ws.send(e.toString()) } catch (_: Throwable) {}
    }

    private fun errorObj(id: String?, code: Int, msg: String, data: Any?): JSONObject {
        val err = JSONObject().put("code", code).put("message", msg)
        if (data != null) err.put("data", data.toString())
        return JSONObject().apply {
            if (id != null) put("id", id)
            put("error", err)
        }
    }

    companion object {
        private const val TAG = "MQAgent.WS"
    }
}

data class JsonRpcRequest(
    val id: String,
    val method: String,
    val params: JSONObject,
)

class RpcError(val code: Int, message: String, val data: Any? = null) : RuntimeException(message)

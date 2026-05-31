package com.momoqun.agent.service

import android.app.Notification
import android.app.PendingIntent
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.momoqun.agent.AgentApp
import com.momoqun.agent.AgentConfig
import com.momoqun.agent.MainActivity
import com.momoqun.agent.R
import com.momoqun.agent.ws.RpcDispatcher
import com.momoqun.agent.ws.WsClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * 常驻前台进程：
 * - 持有 [WsClient]，负责 WebSocket 连接与重连
 * - 转发 RPC 请求到 [RpcDispatcher]
 * - 心跳通过 [WsClient.startHeartbeat] 周期发送
 */
class AgentForegroundService : LifecycleService() {

    @Volatile private var ws: WsClient? = null
    @Volatile private var dispatcher: RpcDispatcher? = null
    /** 当前 WsClient 实际连接的 URL，用于判断配置是否变化。 */
    @Volatile private var currentUrl: String? = null
    /** 当前 master 基址，仅用于通知文案（避免多次 launch 收集器）。 */
    @Volatile private var currentMasterUrl: String = ""
    private var statusCollectorStarted = false
    private val statusFlow = MutableStateFlow("idle")

    override fun onBind(intent: Intent): IBinder? {
        super.onBind(intent)
        return null
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startAgent()
            ACTION_STOP -> stopAgent()
        }
        return START_STICKY
    }

    private fun startAgent() {
        val cfg = AgentConfig.load(this) ?: run {
            broadcast("missing config; aborting", "config missing")
            stopSelf()
            return
        }
        currentMasterUrl = cfg.masterUrl
        startForeground(AgentApp.NOTIFICATION_ID, buildNotification(cfg.masterUrl))
        isRunning = true

        if (dispatcher == null) dispatcher = RpcDispatcher(applicationContext)

        // 通知状态收集器只启动一次；用 currentMasterUrl 取最新地址，避免重建时重复 launch。
        if (!statusCollectorStarted) {
            statusCollectorStarted = true
            lifecycleScope.launch {
                statusFlow.collectLatest { s ->
                    updateNotification("$s — $currentMasterUrl")
                }
            }
        }

        // 配置未变且已在运行 → 复用现有连接；配置变了（或首次）→ 重建。
        if (ws != null && currentUrl == cfg.websocketUrl) return
        ws?.shutdown()
        ws = null

        currentUrl = cfg.websocketUrl
        val client = WsClient(
            url = cfg.websocketUrl,
            onStatus = { s ->
                statusFlow.value = s
                broadcast(s, null)
            },
            onRequest = { req -> dispatcher!!.dispatch(req) },
        )
        ws = client
        client.start()
    }

    private fun stopAgent() {
        ws?.shutdown()
        ws = null
        currentUrl = null
        isRunning = false
        broadcast("stopped", null)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        ws?.shutdown()
        ws = null
        currentUrl = null
        isRunning = false
        super.onDestroy()
    }

    private fun buildNotification(masterUrl: String): Notification {
        val openIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, AgentApp.CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(getString(R.string.notification_text, masterUrl))
            .setContentIntent(openIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        val nm = androidx.core.app.NotificationManagerCompat.from(this)
        val n = NotificationCompat.Builder(this, AgentApp.CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(text)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        try { nm.notify(AgentApp.NOTIFICATION_ID, n) } catch (_: SecurityException) {}
    }

    private fun broadcast(status: String, log: String?) {
        val i = Intent(MainActivity.ACTION_STATUS).apply {
            setPackage(packageName)
            putExtra(MainActivity.EXTRA_STATUS, status)
            if (log != null) putExtra(MainActivity.EXTRA_LOG, log)
        }
        sendBroadcast(i)
    }

    companion object {
        const val ACTION_START = "com.momoqun.agent.START"
        const val ACTION_STOP = "com.momoqun.agent.STOP"

        @Volatile var isRunning: Boolean = false
            internal set
    }
}

package com.momoqun.agent.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import com.momoqun.agent.AgentConfig

/**
 * 让 ops 用 adb 一键推送 master/serial 并自动启动 Agent。
 *
 * ```bash
 * adb shell am broadcast -a com.momoqun.agent.SET_CONFIG \
 *     --es master_url "ws://10.0.2.2:5100" \
 *     --es serial "127.0.0.1_5555" \
 *     --ez autostart true \
 *     -n com.momoqun.agent/.service.ConfigReceiver
 * ```
 *
 * - `master_url`：master 的 WebSocket 基址（不带 `/agent/...` 尾巴）。
 * - `serial`：将作为 master 端 `data/friends/<serial>.json` 的命名键。
 *   推荐写法：把 ADB serial 里的 `:` 换成 `_`，例如 `127.0.0.1_5555`。
 * - `autostart`（可选，默认 true）：写完配置后是否立即把 ForegroundService 拉起来。
 */
class ConfigReceiver : BroadcastReceiver() {

    override fun onReceive(ctx: Context, intent: Intent) {
        if (intent.action != ACTION_SET_CONFIG) return

        val master = intent.getStringExtra(EXTRA_MASTER_URL)?.trim().orEmpty()
        val serial = intent.getStringExtra(EXTRA_SERIAL)?.trim().orEmpty()
        val autostart = intent.getBooleanExtra(EXTRA_AUTOSTART, true)

        if (master.isEmpty() || serial.isEmpty()) {
            Log.w(TAG, "拒绝写入：master_url 或 serial 为空（master='$master' serial='$serial'）")
            return
        }

        AgentConfig.save(ctx, AgentConfig(master, serial))
        Log.i(TAG, "config saved master='$master' serial='$serial' autostart=$autostart")

        if (autostart) {
            val svc = Intent(ctx, AgentForegroundService::class.java).apply {
                action = AgentForegroundService.ACTION_START
            }
            ContextCompat.startForegroundService(ctx, svc)
        }
    }

    companion object {
        const val ACTION_SET_CONFIG = "com.momoqun.agent.SET_CONFIG"
        const val EXTRA_MASTER_URL = "master_url"
        const val EXTRA_SERIAL = "serial"
        const val EXTRA_AUTOSTART = "autostart"

        private const val TAG = "MQAgent.Config"
    }
}

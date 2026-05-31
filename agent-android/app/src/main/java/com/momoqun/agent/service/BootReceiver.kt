package com.momoqun.agent.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.momoqun.agent.AgentConfig

/** 开机自启 — 仅当用户曾保存过 master/serial 配置时。 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        AgentConfig.load(ctx) ?: return
        val svc = Intent(ctx, AgentForegroundService::class.java).apply {
            action = AgentForegroundService.ACTION_START
        }
        ContextCompat.startForegroundService(ctx, svc)
    }
}

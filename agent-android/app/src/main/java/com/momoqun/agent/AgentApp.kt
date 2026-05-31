package com.momoqun.agent

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class AgentApp : Application() {

    override fun onCreate() {
        super.onCreate()
        instance = this
        ensureNotificationChannel()
    }

    private fun ensureNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NotificationManager::class.java) ?: return
        val ch = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel),
            NotificationManager.IMPORTANCE_LOW,
        )
        ch.setShowBadge(false)
        nm.createNotificationChannel(ch)
    }

    companion object {
        const val CHANNEL_ID = "momoqun-agent"
        const val NOTIFICATION_ID = 0x4d51 // "MQ"

        lateinit var instance: AgentApp
            private set
    }
}

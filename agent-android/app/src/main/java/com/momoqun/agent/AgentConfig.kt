package com.momoqun.agent

import android.content.Context

/**
 * 运行时配置：master 地址 + serial。
 *
 * 用 SharedPreferences 持久化，保证设备开机自启时能拿到上次配置。
 */
data class AgentConfig(
    val masterUrl: String,
    val serial: String,
) {
    val websocketUrl: String
        get() {
            val base = masterUrl.trimEnd('/')
            return "$base/agent/$serial"
        }

    companion object {
        private const val PREFS = "agent.config"
        private const val KEY_MASTER = "master_url"
        private const val KEY_SERIAL = "serial"

        fun load(ctx: Context): AgentConfig? {
            val sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val master = sp.getString(KEY_MASTER, null) ?: return null
            val serial = sp.getString(KEY_SERIAL, null) ?: return null
            if (master.isBlank() || serial.isBlank()) return null
            return AgentConfig(master, serial)
        }

        fun save(ctx: Context, cfg: AgentConfig) {
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_MASTER, cfg.masterUrl)
                .putString(KEY_SERIAL, cfg.serial)
                .apply()
        }

        fun clear(ctx: Context) {
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .clear()
                .apply()
        }
    }
}

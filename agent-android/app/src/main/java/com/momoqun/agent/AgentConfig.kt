package com.momoqun.agent

import android.content.Context
import java.net.URLEncoder

/**
 * 运行时配置：master 地址 + serial + 可选 API Token。
 *
 * 用 SharedPreferences 持久化，保证设备开机自启时能拿到上次配置。
 */
data class AgentConfig(
    val masterUrl: String,
    val serial: String,
    val apiToken: String = "",
) {
    val websocketUrl: String
        get() {
            val base = masterUrl.trimEnd('/')
            val path = "$base/agent/$serial"
            val token = apiToken.trim()
            if (token.isEmpty()) return path
            val encoded = URLEncoder.encode(token, Charsets.UTF_8.name())
            return "$path?token=$encoded"
        }

    companion object {
        private const val PREFS = "agent.config"
        private const val KEY_MASTER = "master_url"
        private const val KEY_SERIAL = "serial"
        private const val KEY_TOKEN = "api_token"

        fun load(ctx: Context): AgentConfig? {
            val sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val master = sp.getString(KEY_MASTER, null) ?: return null
            val serial = sp.getString(KEY_SERIAL, null) ?: return null
            if (master.isBlank() || serial.isBlank()) return null
            val token = sp.getString(KEY_TOKEN, "") ?: ""
            return AgentConfig(master, serial, token)
        }

        fun save(ctx: Context, cfg: AgentConfig) {
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_MASTER, cfg.masterUrl)
                .putString(KEY_SERIAL, cfg.serial)
                .putString(KEY_TOKEN, cfg.apiToken)
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

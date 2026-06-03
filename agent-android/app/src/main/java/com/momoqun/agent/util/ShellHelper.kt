package com.momoqun.agent.util

import android.util.Log
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit

/**
 * 以 root 身份在设备本地执行 shell 命令（`su -c`）。
 *
 * 不依赖 master adb、不依赖 AccessibilityService。
 * 设备需已 root（Magisk / LDPlayer 内置 su 等）。
 */
object ShellHelper {
    private const val TAG = "MQAgent.Shell"

    data class Result(val code: Int, val output: String, val stderr: String = "") {
        val ok: Boolean get() = code == 0
    }

    fun exec(cmd: String, timeoutSec: Long = 10): Result {
        val escaped = cmd.replace("'", "'\\''")
        val rootCmd = "su -c '$escaped'"
        Log.d(TAG, "exec: ${rootCmd.take(200)}")
        return try {
            val proc = Runtime.getRuntime().exec(arrayOf("sh", "-c", rootCmd))
            val stdout = BufferedReader(InputStreamReader(proc.inputStream)).use { it.readText() }
            val stderr = BufferedReader(InputStreamReader(proc.errorStream)).use { it.readText() }
            val finished = proc.waitFor(timeoutSec, TimeUnit.SECONDS)
            if (!finished) {
                proc.destroyForcibly()
                Log.w(TAG, "exec timeout (${timeoutSec}s): ${cmd.take(100)}")
                Result(-1, stdout.trim(), "timeout")
            } else {
                val code = proc.exitValue()
                if (code != 0) {
                    Log.w(TAG, "exec failed: code=$code stderr=${stderr.take(200)}")
                }
                Result(code, stdout.trim(), stderr.trim())
            }
        } catch (e: Exception) {
            Log.w(TAG, "exec exception: ${cmd.take(80)}", e)
            Result(-1, "", e.message ?: "exception")
        }
    }

    fun execOk(cmd: String, timeoutSec: Long = 10): Boolean = exec(cmd, timeoutSec).ok
}

package com.momoqun.agent.rpc

import android.util.Log
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit

/**
 * 以 root 身份在设备本地执行 shell 命令（`su -c`）。
 *
 * 不依赖 master adb 通道，不依赖 AccessibilityService。
 * 所有操作（点击、滑动、截图、dump 等）通过此入口以 root 权限执行。
 * 设备需已 root（Magisk / SuperSU 等）。
 */
object ShellViaMaster {
    private const val TAG = "MQAgent.Shell"

    data class Result(val code: Int, val stdout: String, val stderr: String) {
        val ok: Boolean get() = code == 0
    }

    /**
     * 以 root 执行命令，返回退出码 + 输出。
     */
    fun exec(cmd: String, timeoutSec: Long = 10): Result {
        val escaped = cmd.replace("'", "'\\''")
        val rootCmd = "su -c '$escaped'"
        Log.d(TAG, "exec: $rootCmd")
        return try {
            val proc = Runtime.getRuntime().exec(arrayOf("sh", "-c", rootCmd))
            val stdout = BufferedReader(InputStreamReader(proc.inputStream)).use { it.readText() }
            val stderr = BufferedReader(InputStreamReader(proc.errorStream)).use { it.readText() }
            val finished = proc.waitFor(timeoutSec, TimeUnit.SECONDS)
            if (!finished) {
                proc.destroyForcibly()
                Log.w(TAG, "exec timeout (${timeoutSec}s): ${cmd.take(100)}")
                Result(-1, stdout, "timeout")
            } else {
                val code = proc.exitValue()
                Log.d(TAG, "exec done: code=$code stdout=${stdout.take(100)} stderr=${stderr.take(100)}")
                Result(code, stdout, stderr)
            }
        } catch (e: Exception) {
            Log.w(TAG, "exec exception: ${cmd.take(80)}", e)
            Result(-1, "", e.message ?: "exception")
        }
    }

    /**
     * 便捷方法：成功返回 true，失败返回 false。
     */
    fun ok(cmd: String): Boolean = exec(cmd).ok
}

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

    /** App 进程 PATH 常不含 su；adb shell 多为 /system/bin/su 或 /sbin/su。 */
    private val SU_CANDIDATES = listOf(
        "/system/bin/su",
        "/sbin/su",
        "/system/xbin/su",
        "/system/sbin/su",
        "su",
        "/data/adb/magisk/magisk",
    )

    @Volatile
    private var cachedSuPath: String? = null

    data class Result(val code: Int, val output: String, val stderr: String = "") {
        val ok: Boolean get() = code == 0
    }

    fun exec(cmd: String, timeoutSec: Long = 10): Result {
        val suPaths = buildList {
            cachedSuPath?.let { add(it) }
            addAll(SU_CANDIDATES)
        }.distinct()
        var last: Result = Result(-1, "", "no su binary found")
        for (su in suPaths) {
            Log.d(TAG, "exec: $su -c ${cmd.take(200)}")
            val r = execWithSu(su, cmd, timeoutSec)
            val missingSu = r.code == -1 && r.output.isEmpty() &&
                (r.stderr.contains("No such file or directory") ||
                    r.stderr.contains("Cannot run program"))
            if (missingSu) {
                last = r
                continue
            }
            cachedSuPath = su
            return r
        }
        Log.w(TAG, "all su paths failed for: ${cmd.take(80)}")
        return last
    }

    private fun execWithSu(su: String, cmd: String, timeoutSec: Long): Result {
        return try {
            val proc = Runtime.getRuntime().exec(arrayOf(su, "-c", cmd))
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
            Log.w(TAG, "exec exception ($su): ${cmd.take(80)}", e)
            Result(-1, "", e.message ?: "exception")
        }
    }

    fun execOk(cmd: String, timeoutSec: Long = 10): Boolean = exec(cmd, timeoutSec).ok
}

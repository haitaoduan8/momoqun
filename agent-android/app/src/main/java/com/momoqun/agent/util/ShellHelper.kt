package com.momoqun.agent.util

import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * Shell 命令执行工具（替代 AccessibilityService，避免开无障碍导致卡顿）
 */
object ShellHelper {

    data class Result(val code: Int, val output: String)

    fun exec(cmd: String): Result {
        val p = Runtime.getRuntime().exec(arrayOf("sh", "-c", cmd))
        val stdout = BufferedReader(InputStreamReader(p.inputStream)).readText()
        val code = p.waitFor()
        return Result(code, stdout.trim())
    }

    fun execOk(cmd: String): Boolean = exec(cmd).code == 0
}

package com.momoqun.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Bundle
import android.provider.Settings
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.momoqun.agent.databinding.ActivityMainBinding
import com.momoqun.agent.service.AgentForegroundService

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            val status = intent.getStringExtra(EXTRA_STATUS) ?: return
            binding.status.text = status
            val log = intent.getStringExtra(EXTRA_LOG)
            if (!log.isNullOrEmpty()) appendLog(log)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        AgentConfig.load(this)?.let {
            binding.inputMaster.setText(it.masterUrl)
            binding.inputSerial.setText(it.serial)
        }

        binding.btnStart.setOnClickListener { onStart() }
        binding.btnStop.setOnClickListener { onStop() }
        binding.btnOpenA11y.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        binding.btnOpenIme.setOnClickListener {
            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
        }
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter(ACTION_STATUS)
        ContextCompat.registerReceiver(
            this,
            statusReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED,
        )
        refreshButtons()
    }

    override fun onPause() {
        super.onPause()
        try { unregisterReceiver(statusReceiver) } catch (_: Exception) {}
    }

    private fun onStart() {
        val master = binding.inputMaster.text?.toString()?.trim().orEmpty()
        val serial = binding.inputSerial.text?.toString()?.trim().orEmpty()
        if (master.isEmpty() || serial.isEmpty()) {
            binding.status.text = "master / serial 不能为空"
            return
        }
        val cfg = AgentConfig(master, serial)
        AgentConfig.save(this, cfg)

        val intent = Intent(this, AgentForegroundService::class.java).apply {
            action = AgentForegroundService.ACTION_START
        }
        ContextCompat.startForegroundService(this, intent)
        refreshButtons(running = true)
    }

    private fun onStop() {
        val intent = Intent(this, AgentForegroundService::class.java).apply {
            action = AgentForegroundService.ACTION_STOP
        }
        startService(intent)
        refreshButtons(running = false)
    }

    private fun refreshButtons(running: Boolean = AgentForegroundService.isRunning) {
        binding.btnStart.isEnabled = !running
        binding.btnStop.isEnabled = running
    }

    private fun appendLog(line: String) {
        val cur = binding.log.text?.toString().orEmpty()
        val next = if (cur.isEmpty()) line else "$cur\n$line"
        val trimmed = next.lines().takeLast(120).joinToString("\n")
        binding.log.text = trimmed
    }

    companion object {
        const val ACTION_STATUS = "com.momoqun.agent.STATUS"
        const val EXTRA_STATUS = "status"
        const val EXTRA_LOG = "log"
    }
}

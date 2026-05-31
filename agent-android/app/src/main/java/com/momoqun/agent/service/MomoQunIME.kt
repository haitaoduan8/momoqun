package com.momoqun.agent.service

import android.inputmethodservice.InputMethodService
import android.util.Log
import android.view.View
import android.widget.FrameLayout

/**
 * 极简 IME：没有键盘 UI，但必须存在；用于通过 [commitTextToInput] 注入文本。
 *
 * 协议：master 调用 `type_text`，RPC handler 通过 [INSTANCE] 拿到 IME 实例并写入
 * 当前 InputConnection。系统默认 IME 必须被设为 momoqun-ime（用户在设置里切）。
 */
class MomoQunIME : InputMethodService() {

    @Volatile private var visible: Boolean = false

    override fun onCreate() {
        super.onCreate()
        INSTANCE = this
        Log.i(TAG, "MomoQunIME created")
    }

    override fun onDestroy() {
        Log.i(TAG, "MomoQunIME destroyed")
        if (INSTANCE === this) INSTANCE = null
        super.onDestroy()
    }

    override fun onCreateInputView(): View {
        // 透明小条占位（不真做键盘 UI），避免遮挡内容
        val v = FrameLayout(this)
        v.layoutParams = android.view.ViewGroup.LayoutParams(0, 0)
        return v
    }

    override fun onStartInputView(info: android.view.inputmethod.EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        visible = true
    }

    override fun onFinishInputView(finishingInput: Boolean) {
        super.onFinishInputView(finishingInput)
        visible = false
    }

    fun isVisible(): Boolean = visible

    /** 提交一段文本到当前输入焦点。 */
    fun commitTextToInput(text: String): Boolean {
        val ic = currentInputConnection ?: return false
        return try {
            ic.beginBatchEdit()
            ic.commitText(text, 1)
            ic.endBatchEdit()
            true
        } catch (t: Throwable) {
            Log.e(TAG, "commitText failed", t); false
        }
    }

    /** 删除当前输入框已有文本（before+after），方便 master 覆盖式写入。 */
    fun clearCurrentText(): Boolean {
        val ic = currentInputConnection ?: return false
        return try {
            val before = ic.getTextBeforeCursor(MAX_CLEAR, 0)?.length ?: 0
            val after = ic.getTextAfterCursor(MAX_CLEAR, 0)?.length ?: 0
            ic.beginBatchEdit()
            ic.deleteSurroundingText(before, after)
            ic.endBatchEdit()
            true
        } catch (t: Throwable) {
            Log.e(TAG, "clear failed", t); false
        }
    }

    companion object {
        private const val TAG = "MQAgent.IME"
        private const val MAX_CLEAR = 4096

        @Volatile var INSTANCE: MomoQunIME? = null
            private set
    }
}

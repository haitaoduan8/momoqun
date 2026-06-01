package com.momoqun.agent.rpc

import com.momoqun.agent.util.ShellHelper
import org.json.JSONObject

object KeyboardVisibleHandler {
    fun handle(): JSONObject {
        // 通过 dumpsys 检测软键盘是否可见
        val result = ShellHelper.exec("dumpsys input_method | grep mInputShown")
        val visible = result.output.contains("mInputShown=true")
        return JSONObject().put("visible", visible)
    }
}

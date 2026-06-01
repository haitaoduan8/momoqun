package com.momoqun.agent.rpc

import com.momoqun.agent.util.ShellHelper
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object DumpHierarchyHandler {
    private const val TMP_PATH = "/data/local/tmp/_mq_hierarchy.xml"

    fun handle(params: JSONObject): JSONObject {
        // dump 到临时文件
        val dumpOk = ShellHelper.execOk("uiautomator dump $TMP_PATH")
        if (!dumpOk) throw RpcError(-32603, "uiautomator dump failed")

        // 读取文件内容并删除
        val result = ShellHelper.exec("cat $TMP_PATH && rm -f $TMP_PATH")
        if (result.code != 0 || result.output.isEmpty()) {
            throw RpcError(-32603, "failed to read hierarchy dump")
        }

        return JSONObject().put("xml", result.output)
    }
}

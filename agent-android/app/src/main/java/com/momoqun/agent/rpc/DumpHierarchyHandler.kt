package com.momoqun.agent.rpc

import com.momoqun.agent.service.A11yService
import com.momoqun.agent.util.HierarchyXml
import com.momoqun.agent.ws.RpcError
import org.json.JSONObject

object DumpHierarchyHandler {
    fun handle(params: JSONObject): JSONObject {
        val svc = A11yService.INSTANCE
            ?: throw RpcError(-32003, "accessibility service not enabled")
        val root = svc.activeRoot()
        val (w, h) = svc.displaySize()
        val xml = HierarchyXml.serialize(root, w, h, rotation = 0)
        try { root?.recycle() } catch (_: Throwable) {}
        return JSONObject().put("xml", xml)
    }
}

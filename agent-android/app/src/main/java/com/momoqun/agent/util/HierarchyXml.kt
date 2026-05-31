package com.momoqun.agent.util

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo

/**
 * 把 [AccessibilityNodeInfo] 树序列化为 **uiautomator2 兼容**的 XML，
 * 业务侧仍可用 `lxml` 直接 xpath。
 *
 * 字段对齐 `androidx.test.uiautomator.AccessibilityNodeInfoDumper` 输出：
 * - 元素：`<hierarchy rotation="..."><node ...>...</node></hierarchy>`
 * - 属性：index/text/resource-id/class/package/content-desc/checkable/checked/
 *         clickable/enabled/focusable/focused/scrollable/long-clickable/password/
 *         selected/bounds
 *
 * `bounds` 用 `[L,T][R,B]` 格式。
 */
object HierarchyXml {

    fun serialize(root: AccessibilityNodeInfo?, screenW: Int, screenH: Int, rotation: Int = 0): String {
        val sb = StringBuilder(8 * 1024)
        sb.append("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>""").append('\n')
        sb.append("<hierarchy rotation=\"").append(rotation).append("\">\n")
        if (root != null) {
            dumpNode(root, sb, 0, screenW, screenH)
        }
        sb.append("</hierarchy>\n")
        return sb.toString()
    }

    private fun dumpNode(
        node: AccessibilityNodeInfo,
        sb: StringBuilder,
        index: Int,
        screenW: Int,
        screenH: Int,
    ) {
        val cls = (node.className ?: "").toString()
        val pkg = (node.packageName ?: "").toString()
        val rid = (node.viewIdResourceName ?: "").toString()
        val text = (node.text ?: "").toString()
        val desc = (node.contentDescription ?: "").toString()

        val r = Rect()
        node.getBoundsInScreen(r)
        val l = r.left.coerceIn(0, screenW)
        val t = r.top.coerceIn(0, screenH)
        val rr = r.right.coerceIn(0, screenW)
        val rb = r.bottom.coerceIn(0, screenH)

        sb.append("<node")
        attr(sb, "index", index.toString())
        attr(sb, "text", text)
        attr(sb, "resource-id", rid)
        attr(sb, "class", cls)
        attr(sb, "package", pkg)
        attr(sb, "content-desc", desc)
        attr(sb, "checkable", node.isCheckable.toString())
        attr(sb, "checked", node.isChecked.toString())
        attr(sb, "clickable", node.isClickable.toString())
        attr(sb, "enabled", node.isEnabled.toString())
        attr(sb, "focusable", node.isFocusable.toString())
        attr(sb, "focused", node.isFocused.toString())
        attr(sb, "scrollable", node.isScrollable.toString())
        attr(sb, "long-clickable", node.isLongClickable.toString())
        attr(sb, "password", node.isPassword.toString())
        attr(sb, "selected", node.isSelected.toString())
        attr(sb, "bounds", "[$l,$t][$rr,$rb]")

        val childCount = node.childCount
        if (childCount == 0) {
            sb.append("/>\n")
            return
        }
        sb.append(">\n")
        for (i in 0 until childCount) {
            val child = node.getChild(i) ?: continue
            try {
                dumpNode(child, sb, i, screenW, screenH)
            } finally {
                try { child.recycle() } catch (_: Throwable) {}
            }
        }
        sb.append("</node>\n")
    }

    private fun attr(sb: StringBuilder, name: String, value: String) {
        sb.append(' ').append(name).append("=\"").append(escape(value)).append('"')
    }

    private fun escape(s: String): String {
        if (s.isEmpty()) return s
        val sb = StringBuilder(s.length)
        for (c in s) {
            when (c) {
                '&' -> sb.append("&amp;")
                '<' -> sb.append("&lt;")
                '>' -> sb.append("&gt;")
                '"' -> sb.append("&quot;")
                '\'' -> sb.append("&apos;")
                '\n', '\r', '\t' -> sb.append(' ')
                else -> if (c.code in 0x20..0x7E || c.code >= 0x80) sb.append(c)
            }
        }
        return sb.toString()
    }
}

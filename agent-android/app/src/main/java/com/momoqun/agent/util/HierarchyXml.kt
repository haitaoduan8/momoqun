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

    /**
     * 遍历深度上限。平台 `uiautomator dump` 在深层 UI 树上递归序列化会栈溢出崩溃；
     * 这里改用显式栈迭代,并加硬上限作为最后保险。超限子树被截断(写成自闭合 node)。
     */
    private const val MAX_DEPTH = 500

    /** 节点总数上限,防止异常页面(如无限列表)产生超大 XML 拖垮 WS 帧 / 解析。 */
    private const val MAX_NODES = 20_000

    fun serialize(root: AccessibilityNodeInfo?, screenW: Int, screenH: Int, rotation: Int = 0): String {
        val sb = StringBuilder(16 * 1024)
        sb.append("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>""").append('\n')
        sb.append("<hierarchy rotation=\"").append(rotation).append("\">\n")
        if (root != null) {
            dumpIterative(root, sb, screenW, screenH)
        }
        sb.append("</hierarchy>\n")
        return sb.toString()
    }

    /** 单个遍历帧:记录节点、它在父节点中的 index、下一个待处理子节点下标、深度。 */
    private class Frame(
        val node: AccessibilityNodeInfo,
        val index: Int,
        val depth: Int,
    ) {
        var childIdx: Int = 0
        var opened: Boolean = false
        var hasChildrenTag: Boolean = false
    }

    /**
     * 显式栈(堆上)迭代遍历 AccessibilityNodeInfo 树,等价于原递归 `dumpNode`,
     * 但不受线程栈深度限制,且带 [MAX_DEPTH] / [MAX_NODES] 上限。
     * 输出的节点属性与 `androidx.test.uiautomator.AccessibilityNodeInfoDumper` 对齐,业务侧 xpath 不变。
     *
     * 不回收 root(由调用方负责),回收所有经 `getChild` 取得的子节点。
     */
    private fun dumpIterative(
        root: AccessibilityNodeInfo,
        sb: StringBuilder,
        screenW: Int,
        screenH: Int,
    ) {
        val stack = ArrayDeque<Frame>()
        stack.addLast(Frame(root, 0, 0))
        var nodeCount = 0

        while (stack.isNotEmpty()) {
            val f = stack.last()

            if (!f.opened) {
                f.opened = true
                nodeCount++
                appendOpenTag(f.node, sb, f.index, screenW, screenH)
                // 截断条件:达到深度/节点上限时不再展开子树
                val effectiveChildCount =
                    if (f.depth >= MAX_DEPTH || nodeCount >= MAX_NODES) 0 else f.node.childCount
                if (effectiveChildCount == 0) {
                    sb.append("/>\n")
                    finishFrame(f, stack)
                    continue
                }
                sb.append(">\n")
                f.hasChildrenTag = true
            }

            val childCount = f.node.childCount
            if (f.childIdx < childCount && nodeCount < MAX_NODES) {
                val i = f.childIdx
                f.childIdx++
                val child = try { f.node.getChild(i) } catch (_: Throwable) { null } ?: continue
                stack.addLast(Frame(child, i, f.depth + 1))
            } else {
                if (f.hasChildrenTag) sb.append("</node>\n")
                finishFrame(f, stack)
            }
        }
    }

    /** 弹栈并回收节点(root,即 depth==0,不回收,留给调用方)。 */
    private fun finishFrame(f: Frame, stack: ArrayDeque<Frame>) {
        if (f.depth != 0) {
            try { f.node.recycle() } catch (_: Throwable) {}
        }
        stack.removeLast()
    }

    /** 写出 `<node ...属性`(不含结尾的 `>` 或 `/>`,由调用方按是否有子节点决定)。 */
    private fun appendOpenTag(
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

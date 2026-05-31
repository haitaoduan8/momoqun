#!/usr/bin/env bash
# 在所有 ADB 设备上一键启用 momoqun-agent 的无障碍服务 + 输入法。
#
# 适用：模拟器/手机已 root 或允许 adb shell `settings put`。
# - 雷电 / mumu / 夜神 / BlueStacks 默认开 root，可用。
# - 真机 / 未 root 模拟器需在系统设置里手动开启（adb 无权限改 Secure 表）。
#
# 用法：
#   ./scripts/setup_permissions.sh                # 全部设备
#   ./scripts/setup_permissions.sh emulator-5554  # 指定 serial

set -euo pipefail

ADB="${ADB:-adb}"
A11Y_ID="com.momoqun.agent/com.momoqun.agent.service.A11yService"
IME_ID="com.momoqun.agent/com.momoqun.agent.service.MomoQunIME"

target_serials=()
if [[ $# -gt 0 ]]; then
    target_serials=("$@")
else
    mapfile -t target_serials < <("$ADB" devices | awk '$2=="device"{print $1}')
fi

if [[ ${#target_serials[@]} -eq 0 ]]; then
    echo "没有可用 ADB 设备" >&2
    exit 1
fi

for sn in "${target_serials[@]}"; do
    echo
    echo "=== $sn ==="

    # ---- Accessibility ----
    current="$("$ADB" -s "$sn" shell settings get secure enabled_accessibility_services 2>/dev/null | tr -d '\r' || echo '')"
    if [[ "$current" == *"$A11Y_ID"* ]]; then
        echo "  [a11y] 已启用：$A11Y_ID"
    else
        if [[ -z "$current" || "$current" == "null" ]]; then
            new="$A11Y_ID"
        else
            new="$current:$A11Y_ID"
        fi
        "$ADB" -s "$sn" shell settings put secure enabled_accessibility_services "$new" && \
            echo "  [a11y] 启用成功：$A11Y_ID" || \
            echo "  [a11y] 启用失败（可能需要 root；请到设置里手动开）" >&2
        "$ADB" -s "$sn" shell settings put secure accessibility_enabled 1 || true
    fi

    # ---- IME ----
    "$ADB" -s "$sn" shell ime enable "$IME_ID" >/dev/null 2>&1 || true
    "$ADB" -s "$sn" shell ime set "$IME_ID" >/dev/null 2>&1 || true
    selected="$("$ADB" -s "$sn" shell settings get secure default_input_method 2>/dev/null | tr -d '\r' || echo '')"
    if [[ "$selected" == "$IME_ID" ]]; then
        echo "  [ime]  默认输入法 = $IME_ID"
    else
        echo "  [ime]  默认输入法 = $selected（非 momoqun-ime；请手动切）" >&2
    fi
done

echo
echo "全部处理完成。"

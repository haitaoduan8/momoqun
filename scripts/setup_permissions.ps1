<#
.SYNOPSIS
    在 ADB 设备上一键启用 momoqun-agent 的无障碍服务 + 输入法。

.DESCRIPTION
    适用 root 模拟器（雷电 / mumu / 夜神 / BlueStacks）。
    未 root 真机请到系统设置里手动开启。

.EXAMPLE
    .\scripts\setup_permissions.ps1
    .\scripts\setup_permissions.ps1 -Serials @("emulator-5554","127.0.0.1:5557")
#>

[CmdletBinding()]
param(
    [string[]]$Serials,
    [string]$Adb = "adb"
)

$ErrorActionPreference = "Continue"
$A11Y_ID = "com.momoqun.agent/com.momoqun.agent.service.A11yService"
$IME_ID  = "com.momoqun.agent/com.momoqun.agent.service.MomoQunIME"

if (-not $Serials -or $Serials.Count -eq 0) {
    $devicesRaw = & $Adb devices
    $Serials = @()
    foreach ($line in $devicesRaw) {
        if ($line -match '^([^\s]+)\s+device\s*$') { $Serials += $Matches[1] }
    }
}

if ($Serials.Count -eq 0) {
    Write-Error "没有可用 ADB 设备"
    exit 1
}

foreach ($sn in $Serials) {
    Write-Host ""
    Write-Host "=== $sn ===" -ForegroundColor Cyan

    # Accessibility
    $current = (& $Adb -s $sn shell settings get secure enabled_accessibility_services).Trim()
    if ($current -like "*$A11Y_ID*") {
        Write-Host "  [a11y] 已启用：$A11Y_ID"
    } else {
        if ([string]::IsNullOrEmpty($current) -or $current -eq "null") {
            $new = $A11Y_ID
        } else {
            $new = "$current`:$A11Y_ID"
        }
        try {
            & $Adb -s $sn shell settings put secure enabled_accessibility_services $new
            & $Adb -s $sn shell settings put secure accessibility_enabled 1
            Write-Host "  [a11y] 启用成功：$A11Y_ID"
        } catch {
            Write-Warning "  [a11y] 启用失败（可能需要 root）：$_"
        }
    }

    # IME
    & $Adb -s $sn shell ime enable $IME_ID 2>$null | Out-Null
    & $Adb -s $sn shell ime set $IME_ID 2>$null | Out-Null
    $selected = (& $Adb -s $sn shell settings get secure default_input_method).Trim()
    if ($selected -eq $IME_ID) {
        Write-Host "  [ime]  默认输入法 = $IME_ID"
    } else {
        Write-Warning "  [ime]  默认输入法 = $selected（非 momoqun-ime；请手动切）"
    }
}

Write-Host ""
Write-Host "全部处理完成。"

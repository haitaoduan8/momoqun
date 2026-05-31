<#
.SYNOPSIS
    批量在所有 ADB 设备上安装 / 配置 / 启动 momoqun-agent.apk。

.DESCRIPTION
    用于路线 C：APK Agent + Python Master。
    自动遍历 `adb devices` 输出的所有 `device` 状态行，
    按需安装 APK 后通过显式 broadcast 推 master/serial config，
    并由 Agent 自动启动 ForegroundService。

.PARAMETER ApkPath
    momoqun-agent.apk 的本地路径（默认从 EXE 同级的 agent-bundle/ 找）。

.PARAMETER MasterUrl
    master 的 WebSocket 基址，例如 ws://192.168.1.100:5100。
    在模拟器内访问宿主机时：
      - 雷电 / mumu / 夜神 / BlueStacks → 宿主机 LAN IP
      - Android Studio AVD → 10.0.2.2

.PARAMETER SkipInstall
    跳过 APK 安装（仅推 config）。当 APK 已部署、只需切换 master 时用。

.PARAMETER Adb
    adb.exe 路径。默认用 PATH 里的。

.EXAMPLE
    .\scripts\deploy_agent.ps1 -MasterUrl ws://192.168.1.50:5100
#>

[CmdletBinding()]
param(
    [string]$ApkPath = "$PSScriptRoot\..\agent-bundle\app-release.apk",
    [Parameter(Mandatory = $true)] [string]$MasterUrl,
    [switch]$SkipInstall,
    [string]$Adb = "adb"
)

$ErrorActionPreference = "Stop"

function Resolve-Adb {
    param([string]$Adb)
    try { & $Adb version | Out-Null; return $Adb } catch { }
    $candidates = @(
        "$PSScriptRoot\..\adb.exe",
        "$PSScriptRoot\..\agent-bundle\adb.exe",
        "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe",
        "$env:ANDROID_HOME\platform-tools\adb.exe"
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    throw "adb 未找到，请把 adb.exe 放到 PATH 或用 -Adb 指定路径。"
}

$adb = Resolve-Adb -Adb $Adb
Write-Host "[deploy] adb = $adb"
Write-Host "[deploy] master = $MasterUrl"

if (-not $SkipInstall) {
    if (-not (Test-Path $ApkPath)) {
        throw "ApkPath 不存在: $ApkPath`n请先在 Android Studio 里 build agent-android/ 工程产出 app-release.apk。"
    }
    Write-Host "[deploy] apk = $ApkPath"
}

$devicesRaw = & $adb devices
$serials = @()
foreach ($line in $devicesRaw) {
    if ($line -match '^([^\s]+)\s+device\s*$') {
        $serials += $Matches[1]
    }
}

if ($serials.Count -eq 0) {
    throw "adb 没有发现任何 'device' 状态的设备。先把模拟器开起来或 adb connect <ip:port>。"
}

Write-Host "[deploy] 待部署设备: $($serials.Count) 台"
$serials | ForEach-Object { Write-Host "         $_" }

$idx = 0
$ok = 0
$fail = @()
foreach ($sn in $serials) {
    $idx++
    Write-Host ""
    Write-Host "[$idx/$($serials.Count)] $sn -------------------------"
    try {
        if (-not $SkipInstall) {
            Write-Host "  install …"
            & $adb -s $sn install -r -g $ApkPath | Out-Host
        }

        # serial 规范化：把冒号换成下划线，与 master 端 storage 命名一致
        $serialNorm = $sn -replace ':', '_'

        Write-Host "  set config (serial=$serialNorm)"
        & $adb -s $sn shell am broadcast `
            -a com.momoqun.agent.SET_CONFIG `
            --es master_url $MasterUrl `
            --es serial $serialNorm `
            --ez autostart true `
            -n com.momoqun.agent/.service.ConfigReceiver | Out-Host

        $ok++
    } catch {
        Write-Warning "  失败：$_"
        $fail += $sn
    }
}

Write-Host ""
Write-Host "[deploy] 完成。ok=$ok fail=$($fail.Count)"
if ($fail.Count -gt 0) {
    Write-Host "[deploy] 失败设备：" -ForegroundColor Yellow
    $fail | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "[deploy] 后续：在每台模拟器上手动启用 ① 无障碍 'MomoQun Agent' ② 输入法 'MomoQun IME'"
Write-Host "         （这俩需要用户授权，adb 暂无法绕过）"
Write-Host "[deploy] master 自检：curl http://<master_host>:<port>/api/agents"

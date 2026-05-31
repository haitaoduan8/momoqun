#!/usr/bin/env bash
# 批量在所有 ADB 设备上安装 / 配置 / 启动 momoqun-agent.apk。
#
# 用于路线 C：APK Agent + Python Master。
#
# 用法：
#   ./scripts/deploy_agent.sh -m ws://192.168.1.50:5100
#   ./scripts/deploy_agent.sh -m ws://10.0.2.2:5100 -a ./agent-bundle/app-release.apk
#   ./scripts/deploy_agent.sh -m ws://... --skip-install   # 已装过 APK，仅推 config

set -euo pipefail

APK_PATH=""
MASTER_URL=""
SKIP_INSTALL=0
ADB="${ADB:-adb}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--apk) APK_PATH="$2"; shift 2 ;;
        -m|--master) MASTER_URL="$2"; shift 2 ;;
        --skip-install) SKIP_INSTALL=1; shift ;;
        --adb) ADB="$2"; shift 2 ;;
        -h|--help)
            grep -E '^# ' "$0" | sed 's/^# //'
            exit 0 ;;
        *) echo "未知参数: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$MASTER_URL" ]]; then
    echo "缺少 -m/--master ws://host:port" >&2
    exit 1
fi

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
    if [[ -z "$APK_PATH" ]]; then
        # 在 dist 同目录或工程根的 agent-bundle/ 里找
        for p in \
            "$(dirname "$0")/../agent-bundle/app-release.apk" \
            "$(dirname "$0")/../agent-bundle/app-debug.apk" \
            "$(dirname "$0")/../agent-android/app/build/outputs/apk/release/app-release.apk" \
            "$(dirname "$0")/../agent-android/app/build/outputs/apk/debug/app-debug.apk"; do
            if [[ -f "$p" ]]; then APK_PATH="$p"; break; fi
        done
    fi
    if [[ -z "$APK_PATH" || ! -f "$APK_PATH" ]]; then
        echo "找不到 APK；用 -a 指定 或 先 build agent-android/ 工程" >&2
        exit 1
    fi
fi

echo "[deploy] adb    = $ADB"
echo "[deploy] master = $MASTER_URL"
[[ "$SKIP_INSTALL" -eq 0 ]] && echo "[deploy] apk    = $APK_PATH"

mapfile -t SERIALS < <("$ADB" devices | awk '$2=="device"{print $1}')

if [[ ${#SERIALS[@]} -eq 0 ]]; then
    echo "adb 没有发现任何 'device' 状态的设备。" >&2
    exit 1
fi

echo "[deploy] 待部署设备: ${#SERIALS[@]} 台"
printf '         %s\n' "${SERIALS[@]}"

ok=0
fail=()
i=0
for sn in "${SERIALS[@]}"; do
    i=$((i+1))
    echo
    echo "[$i/${#SERIALS[@]}] $sn -------------------------"
    if ! {
        if [[ "$SKIP_INSTALL" -eq 0 ]]; then
            echo "  install …"
            "$ADB" -s "$sn" install -r -g "$APK_PATH"
        fi

        serial_norm="${sn//:/_}"

        echo "  set config (serial=$serial_norm)"
        "$ADB" -s "$sn" shell am broadcast \
            -a com.momoqun.agent.SET_CONFIG \
            --es master_url "$MASTER_URL" \
            --es serial "$serial_norm" \
            --ez autostart true \
            -n com.momoqun.agent/.service.ConfigReceiver
    }; then
        echo "  失败" >&2
        fail+=("$sn")
        continue
    fi
    ok=$((ok+1))
done

echo
echo "[deploy] 完成。ok=$ok fail=${#fail[@]}"
if [[ ${#fail[@]} -gt 0 ]]; then
    echo "[deploy] 失败设备:"
    printf '  %s\n' "${fail[@]}"
fi

cat <<'EOF'

[deploy] 后续：
  1. 在每台模拟器上手动启用 ① 无障碍 "MomoQun Agent" ② 输入法 "MomoQun IME"
     （这俩需要用户授权，adb 暂无法绕过；模拟器 root 时可以用 `settings put` 自动化）
  2. master 自检：curl http://<master_host>:<port>/api/agents
EOF

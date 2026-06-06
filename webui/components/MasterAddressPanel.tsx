'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getMasterAddress,
  addDevice,
  deviceAction,
  type MasterAddress,
  type OnlineAgent,
} from "@/lib/api";
import {
  Server,
  Copy,
  Check,
  Loader2,
  Cpu,
  RefreshCw,
  Wifi,
  Play,
  Pause,
} from "lucide-react";
import { useEffect, useState } from "react";

/**
 * 路线 C：展示 master 连接地址（ws://本机IP:端口，可一键复制下发给模拟器 Agent），
 * 并展示在线 Agent 状态，每个 Agent 旁带「开始」按钮。
 */
export function MasterAddressPanel({
  agents = [],
  onRefreshAgents,
}: {
  agents?: OnlineAgent[];
  onRefreshAgents?: () => void | Promise<void>;
}) {
  const [master, setMaster] = useState<MasterAddress | null>(null);
  const [masterErr, setMasterErr] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [bulkAction, setBulkAction] = useState<"start_all" | "pause_all" | null>(
    null
  );

  // master 地址：拿一次即可（IP/端口运行期不变）
  useEffect(() => {
    let alive = true;
    getMasterAddress()
      .then((m) => {
        if (alive) setMaster(m);
      })
      .catch((e) => {
        if (alive) setMasterErr(e instanceof Error ? e.message : "探测失败");
      });
    return () => {
      alive = false;
    };
  }, []);

  const handleCopy = async (text: string) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(text);
      setTimeout(() => setCopied((c) => (c === text ? null : c)), 1500);
    } catch {
      // 复制失败就让用户手动选中
    }
  };

  const handleStart = async (serial: string) => {
    setStarting(serial);
    try {
      // 先确保设备已添加到 DeviceManager
      await addDevice(serial, serial).catch(() => {});
      // 启动脚本
      await deviceAction("start", serial);
      await onRefreshAgents?.();
    } catch (e) {
      console.error("启动失败:", e);
    } finally {
      setStarting(null);
    }
  };

  const handleBulkAction = async (action: "start_all" | "pause_all") => {
    setBulkAction(action);
    try {
      await deviceAction(action);
      await onRefreshAgents?.();
    } catch (e) {
      console.error("批量操作失败:", e);
    } finally {
      setBulkAction(null);
    }
  };

  const wsUrls = master?.ws_urls ?? [];

  return (
    <Card className="border-glow">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Server className="w-5 h-5 text-accent" />
          Master 地址
          <span className="text-sm font-normal text-muted-foreground ml-2">
            (下发给模拟器 Agent)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* ---- A. master 地址 ---- */}
        {masterErr ? (
          <div className="text-sm px-3 py-2 rounded-lg bg-neon-red/10 text-neon-red break-all">
            探测地址失败：{masterErr}
          </div>
        ) : master === null ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在探测本机地址…
          </div>
        ) : wsUrls.length === 0 ? (
          <div className="text-sm px-3 py-2 rounded-lg bg-neon-red/10 text-neon-red">
            未探测到可用内网地址。请检查网络（仅 VPN / 无网卡时会这样），或手动用
            <span className="font-mono"> ipconfig </span>查 IPv4 后填
            <span className="font-mono"> ws://&lt;IP&gt;:{master.port} </span>。
          </div>
        ) : (
          <div className="space-y-2">
            {wsUrls.map((url, idx) => {
              const isCopied = copied === url;
              return (
                <div
                  key={url}
                  className="flex items-center justify-between gap-3 p-3 rounded-lg bg-bg-card border border-accent/6"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-2 h-2 rounded-full bg-neon-green shrink-0" />
                    <span className="font-mono text-sm text-white truncate">
                      {url}
                    </span>
                    {idx === 0 && (
                      <span className="text-xs text-accent shrink-0 px-1.5 py-0.5 rounded bg-accent/10">
                        推荐
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => handleCopy(url)}
                    title="复制地址"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors shrink-0"
                  >
                    {isCopied ? (
                      <Check className="w-3.5 h-3.5" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                    {isCopied ? "已复制" : "复制"}
                  </button>
                </div>
              );
            })}
            <p className="text-xs text-muted-foreground">
              复制后填到模拟器 Agent 的 master 输入框即可，Agent 会自动拼
              <span className="font-mono"> /agent/&lt;serial&gt;</span>，无需手填后缀。
              {master?.auth_required && (
                <>
                  {" "}
                  若启用鉴权，请在 Agent 填写相同的 API Token。
                </>
              )}
            </p>
            {master?.api_token && (
              <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-bg-card border border-accent/6">
                <span className="text-xs text-muted-foreground shrink-0">API Token</span>
                <span className="font-mono text-sm text-white truncate">{master.api_token}</span>
                <button
                  type="button"
                  onClick={() => handleCopy(master.api_token!)}
                  className="text-xs text-accent shrink-0 hover:underline"
                >
                  复制
                </button>
              </div>
            )}
          </div>
        )}

        {/* ---- B. 在线 Agent 状态 ---- */}
        <div className="pt-1">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Wifi className="w-4 h-4 text-accent" />
            <span className="text-sm font-medium text-white">在线 Agent</span>
            <span className="text-sm text-muted-foreground">
              ({agents.length} 台)
            </span>
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={() => handleBulkAction("start_all")}
                disabled={agents.length === 0 || bulkAction !== null}
                title="为所有在线 Agent 添加设备并启动"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-neon-green/10 text-neon-green rounded-lg hover:bg-neon-green/20 transition-colors disabled:opacity-40"
              >
                {bulkAction === "start_all" ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5" />
                )}
                全部启动
              </button>
              <button
                onClick={() => handleBulkAction("pause_all")}
                disabled={bulkAction !== null}
                title="暂停所有已注册设备"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-neon-yellow/10 text-neon-yellow rounded-lg hover:bg-neon-yellow/20 transition-colors disabled:opacity-40"
              >
                {bulkAction === "pause_all" ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Pause className="w-3.5 h-3.5" />
                )}
                全部暂停
              </button>
              <button
                onClick={() => onRefreshAgents?.()}
                title="刷新在线 Agent"
                disabled={!onRefreshAgents || bulkAction !== null}
                className="text-muted-foreground hover:text-white transition-colors disabled:opacity-40 p-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {agents.length === 0 ? (
            <div className="text-center py-6 text-muted-foreground">
              <Cpu className="w-8 h-8 mx-auto mb-2 opacity-60" />
              <p className="text-sm">暂无 Agent 连接</p>
              <p className="text-xs mt-1">
                检查模拟器 Agent 的 master 是否填了上面的 ws 地址；改地址后已无需先停再启。
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {agents.map((a) => (
                <div
                  key={a.serial}
                  className="flex items-center justify-between gap-3 p-3 rounded-lg bg-bg-card border border-accent/6"
                >
                  <button
                    onClick={() => handleStart(a.serial)}
                    disabled={starting === a.serial}
                    title="添加并启动脚本"
                    className="flex items-center justify-center w-8 h-8 rounded-lg bg-neon-green/10 text-neon-green hover:bg-neon-green/20 transition-colors disabled:opacity-50 shrink-0"
                  >
                    {starting === a.serial ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="w-2 h-2 rounded-full bg-neon-green shrink-0 animate-pulse" />
                    <span className="font-mono text-sm text-white truncate">
                      {a.serial}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                    <span title="连接时长">在线 {Math.round(a.connected_for_s)}s</span>
                    <span
                      title="空闲时长（心跳间隔）"
                      className={a.idle_for_s > 30 ? "text-neon-red" : ""}
                    >
                      空闲 {Math.round(a.idle_for_s)}s
                    </span>
                    {a.pending_rpc > 0 && (
                      <span title="待处理 RPC">挂起 {a.pending_rpc}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

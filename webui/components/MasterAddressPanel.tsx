'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getMasterAddress,
  getAgents,
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
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * 路线 C：展示 master 连接地址（ws://本机IP:端口，可一键复制下发给模拟器 Agent），
 * 并轮询在线 Agent 状态，直接回答“哪些模拟器连上了”。
 */
export function MasterAddressPanel() {
  const [master, setMaster] = useState<MasterAddress | null>(null);
  const [masterErr, setMasterErr] = useState<string | null>(null);
  const [agents, setAgents] = useState<OnlineAgent[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

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

  // 在线 agent：轮询
  const refreshAgents = useCallback(async () => {
    try {
      const { agents } = await getAgents();
      setAgents(agents || []);
    } catch {
      // 静默：master 还没起或网络抖动时不打扰
    }
  }, []);

  useEffect(() => {
    refreshAgents();
    const timer = setInterval(refreshAgents, 4000);
    return () => clearInterval(timer);
  }, [refreshAgents]);

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
            </p>
          </div>
        )}

        {/* ---- B. 在线 Agent 状态 ---- */}
        <div className="pt-1">
          <div className="flex items-center gap-2 mb-2">
            <Wifi className="w-4 h-4 text-accent" />
            <span className="text-sm font-medium text-white">在线 Agent</span>
            <span className="text-sm text-muted-foreground">
              ({agents.length} 台)
            </span>
            <button
              onClick={refreshAgents}
              title="刷新在线 Agent"
              className="ml-auto text-muted-foreground hover:text-white transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
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
                  <div className="flex items-center gap-2 min-w-0">
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

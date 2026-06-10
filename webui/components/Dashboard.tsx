'use client';

import { Card, CardContent } from "@/components/ui/card";
import {
  deviceAction,
  removeDevice,
  dismissAccountCheck,
  type Device,
  type Stats,
  type AccountCheckStatus,
} from "@/lib/api";
import {
  Smartphone,
  Settings,
  Shield,
  Activity,
  Play,
  Pause,
  Square,
  Trash2,
  RefreshCw,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { useState } from "react";

export type DashboardViewProps = {
  devices: Device[];
  stats: Stats | null;
  accountCheck: AccountCheckStatus | null;
  loading: boolean;
  refresh: () => void | Promise<void>;
};

// 设备卡片组件
function DeviceCard({
  name,
  serial,
  status,
  rounds,
  friends,
  statusHint,
  onStart,
  onPause,
  onStop,
  onRemove,
}: {
  name: string;
  serial: string;
  status: "running" | "paused" | "stopped" | "error" | "waiting_agent";
  rounds: number;
  friends: number;
  statusHint?: string;
  onStart: () => void | Promise<void>;
  onPause: () => void | Promise<void>;
  onStop: () => void | Promise<void>;
  onRemove: () => void | Promise<void>;
}) {
  const [loading, setLoading] = useState<string | null>(null);

  const statusColors = {
    running: "bg-neon-green",
    paused: "bg-neon-yellow",
    stopped: "bg-gray-500",
    error: "bg-neon-red",
    waiting_agent: "bg-neon-yellow animate-pulse",
  };

  const statusLabels = {
    running: "运行中",
    paused: "已暂停",
    stopped: "已停止",
    error: "错误",
    waiting_agent: "等待 Agent",
  };

  const handleAction = async (action: string, fn: () => void | Promise<void>) => {
    setLoading(action);
    try {
      await fn();
    } finally {
      setLoading(null);
    }
  };

  return (
    <Card className="relative overflow-hidden border-glow hover:border-glow-bright transition-all duration-300">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
              <Smartphone className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h3 className="font-semibold text-white">{name}</h3>
              <p className="text-xs text-muted-foreground font-mono">{serial}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${statusColors[status]} shadow-lg`} />
            <span className="text-sm text-muted-foreground">
              {statusLabels[status]}
            </span>
          </div>
        </div>
        {statusHint && (
          <p className="text-xs text-neon-yellow mb-3">{statusHint}</p>
        )}

        <div className="flex gap-4 mb-4 text-sm">
          <div>
            <span className="text-muted-foreground">轮次:</span>{" "}
            <span className="text-white font-semibold">{rounds}</span>
          </div>
          <div>
            <span className="text-muted-foreground">好友:</span>{" "}
            <span className="text-white font-semibold">{friends}</span>
          </div>
        </div>

        <div className="flex gap-2">
          {status === "running" ? (
            <button
              onClick={() => handleAction("pause", onPause)}
              disabled={loading !== null}
              className="flex-1 flex items-center justify-center gap-2 py-2 bg-neon-yellow/10 text-neon-yellow rounded-lg hover:bg-neon-yellow/20 transition-colors disabled:opacity-50"
            >
              {loading === "pause" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Pause className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">暂停</span>
            </button>
          ) : (
            <button
              onClick={() => handleAction("start", onStart)}
              disabled={loading !== null || status === "waiting_agent"}
              className="flex-1 flex items-center justify-center gap-2 py-2 bg-neon-green/10 text-neon-green rounded-lg hover:bg-neon-green/20 transition-colors disabled:opacity-50"
            >
              {loading === "start" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">
                {status === "paused" ? "继续" : "开始"}
              </span>
            </button>
          )}
          {(status === "running" || status === "paused") && (
            <button
              onClick={() => handleAction("stop", onStop)}
              disabled={loading !== null}
              title="停止线程，再次开始将重新上号"
              className="flex items-center justify-center gap-2 py-2 px-3 bg-gray-500/10 text-gray-300 rounded-lg hover:bg-gray-500/20 transition-colors disabled:opacity-50"
            >
              {loading === "stop" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Square className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">停止</span>
            </button>
          )}
          <button
            onClick={() => handleAction("remove", onRemove)}
            disabled={loading !== null}
            className="flex items-center justify-center gap-2 py-2 px-3 bg-neon-red/10 text-neon-red rounded-lg hover:bg-neon-red/20 transition-colors disabled:opacity-50"
          >
            {loading === "remove" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Trash2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card className="relative overflow-hidden border-glow">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold text-white mt-1">{value}</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center">
            <Icon className="w-6 h-6 text-accent" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function Dashboard({
  devices,
  stats,
  accountCheck,
  loading: devicesLoading,
  refresh,
}: DashboardViewProps) {
  const [bulkAction, setBulkAction] = useState<
    "start_all" | "pause_all" | "stop_all" | null
  >(null);

  const handleStart = async (serial: string) => {
    await deviceAction("start", serial);
    await refresh();
  };

  const handleResume = async (serial: string) => {
    await deviceAction("resume", serial);
    await refresh();
  };

  const handlePause = async (serial: string) => {
    await deviceAction("pause", serial);
    await refresh();
  };

  const handleStop = async (serial: string) => {
    await deviceAction("stop", serial);
    await refresh();
  };

  const handleRemove = async (serial: string) => {
    await removeDevice(serial);
    await refresh();
  };

  const handleDismiss = async (serial: string) => {
    await dismissAccountCheck(serial);
    await refresh();
  };

  const handleBulkAction = async (
    action: "start_all" | "pause_all" | "stop_all"
  ) => {
    setBulkAction(action);
    try {
      await deviceAction(action);
      await refresh();
    } finally {
      setBulkAction(null);
    }
  };

  const totalDevices = devices.length;
  const runningDevices = devices.filter((d) => d.state === "running").length;
  const totalFriends = devices.reduce((sum, d) => sum + (d.friends_total || 0), 0);
  const abnormalAccounts =
    accountCheck?.devices.filter((d) =>
      ["abnormal", "unknown", "error"].includes(d.account_status)
    ) || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="在线设备"
          value={devicesLoading ? "..." : totalDevices}
          icon={Smartphone}
        />
        <StatCard
          title="运行中"
          value={devicesLoading ? "..." : runningDevices}
          icon={Activity}
        />
        <StatCard
          title="总好友数"
          value={devicesLoading ? "..." : totalFriends.toLocaleString()}
          icon={Shield}
        />
        <StatCard
          title="本轮新增好友"
          value={devicesLoading || !stats ? "..." : (stats.friends_this_round ?? 0)}
          icon={RefreshCw}
        />
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <h2 className="text-xl font-semibold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-accent" />
            设备管理
            <span className="text-sm font-normal text-muted-foreground ml-2">
              ({totalDevices} 台)
            </span>
          </h2>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => handleBulkAction("start_all")}
              disabled={bulkAction !== null}
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
              disabled={bulkAction !== null || totalDevices === 0}
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
              onClick={() => handleBulkAction("stop_all")}
              disabled={bulkAction !== null || totalDevices === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-500/10 text-gray-300 rounded-lg hover:bg-gray-500/20 transition-colors disabled:opacity-40"
            >
              {bulkAction === "stop_all" ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Square className="w-3.5 h-3.5" />
              )}
              全部停止
            </button>
          </div>
        </div>

        {devicesLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-accent animate-spin" />
          </div>
        ) : devices.length === 0 ? (
          <Card className="border-glow">
            <CardContent className="p-12 text-center">
              <Smartphone className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">暂无设备</p>
              <p className="text-sm text-muted-foreground mt-2">
                请在上方「在线 Agent」面板点击 ▶ 按钮启动设备
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {devices.map((device) => {
              const waiting =
                device.current_phase === "waiting_agent" ||
                (device.error || "").includes("Agent");
              const displayStatus = waiting ? "waiting_agent" : device.state;
              const statusHint = waiting
                ? device.error || "等待 Agent 连接…"
                : device.state === "paused" && device.error
                  ? device.error
                  : undefined;
              return (
                <DeviceCard
                  key={device.serial}
                  name={device.name || device.serial}
                  serial={device.serial}
                  status={
                    displayStatus as
                      | "running"
                      | "paused"
                      | "stopped"
                      | "error"
                      | "waiting_agent"
                  }
                  statusHint={statusHint}
                  rounds={device.round_number || 0}
                  friends={device.friends_total || 0}
                  onStart={() =>
                    device.state === "paused"
                      ? handleResume(device.serial)
                      : handleStart(device.serial)
                  }
                  onPause={() => handlePause(device.serial)}
                  onStop={() => handleStop(device.serial)}
                  onRemove={() => handleRemove(device.serial)}
                />
              );
            })}
          </div>
        )}
      </div>

      {abnormalAccounts.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-neon-red" />
            异常账号
            <span className="text-sm font-normal text-neon-red ml-2">
              ({abnormalAccounts.length})
            </span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {abnormalAccounts.map((account) => (
              <Card
                key={account.serial}
                className="border-neon-red/20 hover:border-neon-red/40 transition-colors"
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-mono text-sm text-white">{account.serial}</p>
                      <p className="text-xs text-neon-red mt-1">
                        {account.account_status === "abnormal"
                          ? "账号异常"
                          : account.account_status === "error"
                            ? "检测失败"
                            : "未知状态"}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDismiss(account.serial)}
                      className="px-3 py-1 text-xs bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors"
                    >
                      已处理
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

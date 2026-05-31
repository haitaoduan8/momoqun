'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAccountCheck } from "@/lib/hooks";
import { updateAccountCheckConfig, triggerAccountCheck, dismissAccountCheck } from "@/lib/api";
import { Shield, AlertTriangle, CheckCircle, Loader2, Play } from "lucide-react";
import { useState } from "react";

export function AccountCheckPanel() {
  const { status, loading, refresh } = useAccountCheck();
  const [updating, setUpdating] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const abnormalAccounts =
    status?.devices.filter((d) =>
      ["abnormal", "unknown", "error"].includes(d.account_status)
    ) || [];

  const handleToggle = async (enabled: boolean) => {
    setUpdating(true);
    try {
      await updateAccountCheckConfig({ enabled });
      refresh();
    } finally {
      setUpdating(false);
    }
  };

  const handleIntervalChange = async (minutes: number) => {
    setUpdating(true);
    try {
      await updateAccountCheckConfig({ interval_minutes: minutes });
      refresh();
    } finally {
      setUpdating(false);
    }
  };

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await triggerAccountCheck();
      refresh();
    } finally {
      setTriggering(false);
    }
  };

  const handleDismiss = async (serial: string) => {
    await dismissAccountCheck(serial);
    refresh();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 配置卡片 */}
      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-accent" />
            账号检测设置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 启用开关 */}
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-white">启用自动检测</p>
              <p className="text-sm text-muted-foreground">定期自动检测账号状态</p>
            </div>
            <button
              onClick={() => handleToggle(!status?.config.enabled)}
              disabled={updating}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                status?.config.enabled ? "bg-accent" : "bg-gray-600"
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  status?.config.enabled ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {/* 检测周期 */}
          <div>
            <label className="text-sm text-muted-foreground">检测周期</label>
            <div className="grid grid-cols-4 gap-2 mt-2">
              {[15, 30, 60, 120].map((minutes) => (
                <button
                  key={minutes}
                  onClick={() => handleIntervalChange(minutes)}
                  disabled={updating}
                  className={`py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                    status?.config.interval_minutes === minutes
                      ? "bg-accent text-black"
                      : "bg-bg-card border border-accent/6 text-muted-foreground hover:text-white"
                  }`}
                >
                  {minutes}分钟
                </button>
              ))}
            </div>
          </div>

          {/* 立即检测 */}
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="w-full flex items-center justify-center gap-2 py-3 bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors disabled:opacity-50"
          >
            {triggering ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            立即检测一次
          </button>
        </CardContent>
      </Card>

      {/* 异常账号列表 */}
      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-neon-red" />
            异常账号
            {abnormalAccounts.length > 0 && (
              <span className="text-sm font-normal text-neon-red ml-2">
                ({abnormalAccounts.length})
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {abnormalAccounts.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle className="w-12 h-12 text-neon-green mx-auto mb-4" />
              <p className="text-muted-foreground">暂无异常账号</p>
            </div>
          ) : (
            <div className="space-y-4">
              {abnormalAccounts.map((account) => (
                <div
                  key={account.serial}
                  className="flex items-center justify-between p-4 rounded-lg bg-bg-card border border-neon-red/20"
                >
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
                    className="px-4 py-2 text-xs bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors"
                  >
                    已处理
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

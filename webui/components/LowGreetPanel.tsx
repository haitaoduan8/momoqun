"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  clearLowGreetAccounts,
  getLowGreetAccounts,
  type LowGreetEntry,
} from "@/lib/api";

function formatTime(ts: number): string {
  if (!ts) return "-";
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

export function LowGreetPanel() {
  const [entries, setEntries] = useState<LowGreetEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await getLowGreetAccounts();
      setEntries(res.entries || []);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const handleClear = async () => {
    if (!entries.length) return;
    if (!window.confirm(`确定清空 ${entries.length} 条低招呼账号记录？`)) return;
    setClearing(true);
    try {
      await clearLowGreetAccounts();
      await refresh();
    } finally {
      setClearing(false);
    }
  };

  return (
    <Card className="bg-bg-card border-accent/6">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="text-white flex items-center gap-2 text-base">
          <AlertTriangle className="w-4 h-4 text-neon-red" />
          低招呼账号登记
        </CardTitle>
        <button
          type="button"
          onClick={handleClear}
          disabled={clearing || entries.length === 0}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border border-accent/20 text-muted-foreground hover:text-white hover:border-accent/40 disabled:opacity-40"
        >
          <Trash2 className="w-4 h-4" />
          手动清空
        </button>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-3">
          发完动态后超过「低招呼登记等待」分钟、招呼仍低于首批阈值时自动登记；仅手动清空会移除，重启后仍保留。
        </p>
        {loading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无记录</p>
        ) : (
          <ul className="space-y-2 max-h-48 overflow-y-auto">
            {entries.map((item) => (
              <li
                key={`${item.filename}-${item.reported_at}`}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-lg bg-bg-input border border-accent/6"
              >
                <span className="text-white font-mono text-sm">{item.filename}</span>
                <span className="text-xs text-muted-foreground">
                  {item.device_name || item.serial || "—"} · {formatTime(item.reported_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

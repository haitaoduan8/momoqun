'use client';

import { Card, CardContent } from "@/components/ui/card";
import { Terminal, ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { getLogs } from "@/lib/api";

type LogType = "info" | "success" | "error" | "warning";

interface LogEntry {
  time: string;
  message: string;
  type: LogType;
}

// 后端日志级别 → UI 类型
function levelToType(level: string): LogType {
  const l = (level || "").toUpperCase();
  if (l === "ERROR" || l === "CRITICAL") return "error";
  if (l === "WARNING" || l === "WARN") return "warning";
  return "info";
}

export function LogArea() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [expanded, setExpanded] = useState(true);
  // 本地隐藏游标：清空只影响本会话视图，不影响后端缓冲
  const [hiddenCount, setHiddenCount] = useState(0);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // 轮询后端真实运行日志
  useEffect(() => {
    let active = true;
    const fetchLogs = async () => {
      try {
        const { logs: raw } = await getLogs(300);
        if (!active) return;
        setLogs(
          raw.map((entry) => ({
            time: entry.time,
            message: entry.name ? `${entry.name}: ${entry.message}` : entry.message,
            type: levelToType(entry.level),
          }))
        );
      } catch {
        // 后端未启动 / 网络错误时静默，下次轮询重试
      }
    };
    fetchLogs();
    const timer = setInterval(fetchLogs, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const visibleLogs = logs.slice(hiddenCount);

  // 自动滚动到底部
  useEffect(() => {
    if (expanded) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [visibleLogs.length, expanded]);

  const clearLogs = () => {
    setHiddenCount(logs.length);
  };

  const typeColors = {
    info: "text-muted-foreground",
    success: "text-neon-green",
    error: "text-neon-red",
    warning: "text-neon-yellow",
  };

  const typePrefix = {
    info: "ℹ",
    success: "✓",
    error: "✗",
    warning: "⚠",
  };

  return (
    <Card className="relative overflow-hidden border-glow" style={{ height: '450px' }}>
      <CardContent className="p-0 h-full flex flex-col">
        {/* 标题栏 */}
        <div
          className="flex items-center justify-between p-4 cursor-pointer hover:bg-bg-hover/50 transition-colors shrink-0"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <Terminal className="w-4 h-4 text-accent" />
            </div>
            <h2 className="text-lg font-semibold text-white">运行日志</h2>
            <span className="text-xs text-muted-foreground bg-bg-elevated px-2 py-1 rounded">
              {visibleLogs.length} 条
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                clearLogs();
              }}
              className="p-2 text-muted-foreground hover:text-neon-red transition-colors rounded-lg hover:bg-bg-hover"
              title="清空日志"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            {expanded ? (
              <ChevronUp className="w-5 h-5 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-5 h-5 text-muted-foreground" />
            )}
          </div>
        </div>

        {/* 日志内容 */}
        {expanded && (
          <div className="px-4 pb-4 flex-1 min-h-0">
            <div className="bg-black/50 rounded-xl p-4 h-full overflow-y-auto font-mono text-sm">
              {visibleLogs.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  暂无日志
                </div>
              ) : (
                <div className="space-y-1">
                  {visibleLogs.map((log, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <span className="text-muted-foreground shrink-0">
                        [{log.time}]
                      </span>
                      <span className={typeColors[log.type]}>
                        {typePrefix[log.type]}
                      </span>
                      <span className={typeColors[log.type]}>
                        {log.message}
                      </span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

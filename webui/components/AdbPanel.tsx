'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getAdbDevices,
  connectAdb,
  disconnectAdb,
  initAdb,
  addDevice,
  type AdbDevice,
} from "@/lib/api";
import { useDevices } from "@/lib/hooks";
import {
  Usb,
  Plus,
  Link2,
  Unplug,
  RefreshCw,
  Loader2,
  Download,
  CheckCircle2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Feedback = { type: "ok" | "err"; text: string } | null;

export function AdbPanel() {
  const [adbDevices, setAdbDevices] = useState<AdbDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [address, setAddress] = useState("");
  const [connecting, setConnecting] = useState(false);
  // 每台设备的进行中操作：key = `${serial}:${action}`
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState<Feedback>(null);

  // 已加入任务的设备（用于标记「已添加」）
  const { devices: taskDevices, refresh: refreshTaskDevices } = useDevices();
  const addedSerials = new Set(taskDevices.map((d) => d.serial));

  const scan = useCallback(async (showSpinner = false) => {
    if (showSpinner) setScanning(true);
    try {
      const { devices } = await getAdbDevices();
      setAdbDevices(devices || []);
    } catch (err) {
      setFeedback({ type: "err", text: err instanceof Error ? err.message : "扫描失败" });
    } finally {
      if (showSpinner) setScanning(false);
    }
  }, []);

  useEffect(() => {
    scan();
    const timer = setInterval(() => scan(), 5000);
    return () => clearInterval(timer);
  }, [scan]);

  const setBusyFor = (serial: string, action: string, value: boolean) =>
    setBusy((prev) => ({ ...prev, [`${serial}:${action}`]: value }));

  const handleConnect = async () => {
    const addr = address.trim();
    if (!addr) return;
    setConnecting(true);
    setFeedback(null);
    try {
      const res = await connectAdb(addr);
      if (res.ok) {
        setFeedback({ type: "ok", text: `已连接 ${addr}` });
        setAddress("");
        await scan();
      } else {
        setFeedback({ type: "err", text: res.error || `连接 ${addr} 失败` });
      }
    } catch (err) {
      setFeedback({ type: "err", text: err instanceof Error ? err.message : "连接失败" });
    } finally {
      setConnecting(false);
    }
  };

  const handleAdd = async (serial: string) => {
    setBusyFor(serial, "add", true);
    setFeedback(null);
    try {
      const res = await addDevice(serial);
      if (res.ok) {
        setFeedback({ type: "ok", text: `已添加设备 ${serial}` });
        refreshTaskDevices();
      } else {
        setFeedback({ type: "err", text: res.error || "添加失败" });
      }
    } catch (err) {
      setFeedback({ type: "err", text: err instanceof Error ? err.message : "添加失败" });
    } finally {
      setBusyFor(serial, "add", false);
    }
  };

  const handleInit = async (serial: string) => {
    setBusyFor(serial, "init", true);
    setFeedback(null);
    try {
      const res = await initAdb(serial);
      if (res.ok) {
        setFeedback({ type: "ok", text: `${serial} 初始化完成` });
      } else {
        setFeedback({ type: "err", text: res.error || "初始化失败" });
      }
    } catch (err) {
      setFeedback({ type: "err", text: err instanceof Error ? err.message : "初始化失败" });
    } finally {
      setBusyFor(serial, "init", false);
    }
  };

  const handleDisconnect = async (serial: string) => {
    setBusyFor(serial, "disconnect", true);
    setFeedback(null);
    try {
      await disconnectAdb(serial);
      setFeedback({ type: "ok", text: `已断开 ${serial}` });
      await scan();
    } catch (err) {
      setFeedback({ type: "err", text: err instanceof Error ? err.message : "断开失败" });
    } finally {
      setBusyFor(serial, "disconnect", false);
    }
  };

  // 仅网络设备（含端口）可断开
  const isNetworkSerial = (serial: string) => serial.includes(":");

  return (
    <Card className="border-glow">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Usb className="w-5 h-5 text-accent" />
          ADB 设备连接
          <span className="text-sm font-normal text-muted-foreground ml-2">
            ({adbDevices.length} 台在线)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* 网络连接 */}
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleConnect();
            }}
            placeholder="网络地址，如 127.0.0.1:5555"
            className="flex-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-accent/30"
          />
          <button
            onClick={handleConnect}
            disabled={connecting || !address.trim()}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors disabled:opacity-50"
          >
            {connecting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Link2 className="w-4 h-4" />
            )}
            <span className="text-sm font-medium">连接</span>
          </button>
          <button
            onClick={() => scan(true)}
            disabled={scanning}
            title="刷新设备列表"
            className="flex items-center justify-center gap-2 px-4 py-2 bg-bg-card border border-accent/6 text-muted-foreground rounded-lg hover:text-white hover:bg-bg-hover transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${scanning ? "animate-spin" : ""}`} />
            <span className="text-sm font-medium">刷新</span>
          </button>
        </div>

        {/* 反馈信息 */}
        {feedback && (
          <div
            className={`text-sm px-3 py-2 rounded-lg break-all ${
              feedback.type === "ok"
                ? "bg-neon-green/10 text-neon-green"
                : "bg-neon-red/10 text-neon-red"
            }`}
          >
            {feedback.text}
          </div>
        )}

        {/* 设备列表 */}
        {adbDevices.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Usb className="w-10 h-10 mx-auto mb-3 opacity-60" />
            <p>未检测到 ADB 设备</p>
            <p className="text-xs mt-1">请连接模拟器/真机，或在上方输入网络地址连接</p>
          </div>
        ) : (
          <div className="space-y-2">
            {adbDevices.map((dev) => {
              const added = addedSerials.has(dev.serial);
              return (
                <div
                  key={dev.serial}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg bg-bg-card border border-accent/6"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-neon-green shrink-0" />
                      <span className="font-mono text-sm text-white truncate">
                        {dev.serial}
                      </span>
                      {added && (
                        <span className="flex items-center gap-1 text-xs text-accent shrink-0">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          已添加
                        </span>
                      )}
                    </div>
                    {dev.info && (
                      <p className="text-xs text-muted-foreground mt-1 truncate">
                        {dev.info}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleInit(dev.serial)}
                      disabled={busy[`${dev.serial}:init`]}
                      title="安装 ATX agent / 推送 u2.jar / 切换输入法"
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-electric/10 text-electric rounded-lg hover:bg-electric/20 transition-colors disabled:opacity-50"
                    >
                      {busy[`${dev.serial}:init`] ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )}
                      初始化
                    </button>
                    <button
                      onClick={() => handleAdd(dev.serial)}
                      disabled={added || busy[`${dev.serial}:add`]}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors disabled:opacity-50"
                    >
                      {busy[`${dev.serial}:add`] ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Plus className="w-3.5 h-3.5" />
                      )}
                      {added ? "已添加" : "添加"}
                    </button>
                    {isNetworkSerial(dev.serial) && (
                      <button
                        onClick={() => handleDisconnect(dev.serial)}
                        disabled={busy[`${dev.serial}:disconnect`]}
                        title="断开网络连接"
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-neon-red/10 text-neon-red rounded-lg hover:bg-neon-red/20 transition-colors disabled:opacity-50"
                      >
                        {busy[`${dev.serial}:disconnect`] ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Unplug className="w-3.5 h-3.5" />
                        )}
                        断开
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

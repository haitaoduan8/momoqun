'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  deployAgentInit,
  getAgents,
  getMasterAddress,
  listInitDevices,
  previewPushBatch,
  pushBatch,
  pushFile,
  type InitAdbDevice,
  type OnlineAgent,
} from "@/lib/api";
import {
  Check,
  Copy,
  FolderOpen,
  Loader2,
  RefreshCw,
  Rocket,
  Upload,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

function agentSerialPreview(adbSerial: string): string {
  return adbSerial.includes(":") ? adbSerial.replace(/:/g, "_") : adbSerial;
}

export function InitPanel() {
  const [masterUrl, setMasterUrl] = useState("");
  const [masterErr, setMasterErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [devices, setDevices] = useState<InitAdbDevice[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [agents, setAgents] = useState<OnlineAgent[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deviceErr, setDeviceErr] = useState<string | null>(null);

  const [installApk, setInstallApk] = useState(false);
  const [apkPath, setApkPath] = useState("agent-bundle/app-release.apk");

  const [localDir, setLocalDir] = useState("");
  const [localFile, setLocalFile] = useState("");
  const [remoteDir, setRemoteDir] = useState("/sdcard/Download");
  const [pushing, setPushing] = useState(false);

  const [logs, setLogs] = useState<string[]>([]);
  const [deployResults, setDeployResults] = useState<
    Array<{ adb_serial: string; agent_serial?: string; ok: boolean; error?: string | null }>
  >([]);

  const onlineAgentSerials = useMemo(
    () => new Set(agents.map((a) => a.serial)),
    [agents]
  );

  const appendLog = useCallback((line: string) => {
    const ts = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    setLogs((prev) => [...prev.slice(-199), `[${ts}] ${line}`]);
  }, []);

  const refreshAgents = useCallback(async () => {
    try {
      const { agents: list } = await getAgents();
      setAgents(list);
    } catch (e) {
      appendLog(`拉取在线 Agent 失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  }, [appendLog]);

  const refreshDevices = useCallback(async () => {
    setLoadingDevices(true);
    setDeviceErr(null);
    try {
      const res = await listInitDevices();
      if (!res.ok) {
        setDeviceErr(res.error || "刷新设备失败");
        setDevices([]);
        return;
      }
      setDevices(res.devices);
      const online = res.devices.filter((d) => d.state === "device");
      setSelected(new Set(online.map((d) => d.adb_serial)));
      appendLog(`已刷新 ${res.devices.length} 台 ADB 设备（${online.length} 台在线）`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setDeviceErr(msg);
      appendLog(`刷新设备失败: ${msg}`);
    } finally {
      setLoadingDevices(false);
    }
  }, [appendLog]);

  useEffect(() => {
    let alive = true;
    getMasterAddress()
      .then((m) => {
        if (!alive) return;
        const url = m.ws_urls?.[0] || "";
        setMasterUrl(url);
      })
      .catch((e) => {
        if (alive) setMasterErr(e instanceof Error ? e.message : "获取 Master 地址失败");
      });
    refreshDevices();
    refreshAgents();
    return () => {
      alive = false;
    };
  }, [refreshDevices, refreshAgents]);

  const toggleSelect = (serial: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(serial)) next.delete(serial);
      else next.add(serial);
      return next;
    });
  };

  const toggleAll = () => {
    const online = devices.filter((d) => d.state === "device").map((d) => d.adb_serial);
    if (selected.size === online.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(online));
    }
  };

  const selectedSerials = useMemo(() => Array.from(selected), [selected]);

  const handleCopyMaster = async () => {
    if (!masterUrl) return;
    try {
      await navigator.clipboard.writeText(masterUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      appendLog("复制失败，请手动选中地址");
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    setDeployResults([]);
    try {
      const res = await deployAgentInit({
        serials: selectedSerials.length ? selectedSerials : undefined,
        master_url: masterUrl || undefined,
        install_apk: installApk,
        apk_path: installApk ? apkPath : undefined,
      });
      if (res.logs?.length) {
        res.logs.forEach((l) => appendLog(l));
      }
      if (res.results) {
        setDeployResults(res.results);
      }
      appendLog(`配置下发完成：成功 ${res.success ?? 0}，失败 ${res.fail ?? 0}`);
      await refreshAgents();
    } catch (e) {
      appendLog(`下发失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setDeploying(false);
    }
  };

  const handlePushBatch = async () => {
    if (!localDir.trim()) {
      appendLog("请填写本地文件夹路径（Master 宿主机路径）");
      return;
    }
    setPushing(true);
    try {
      const preview = await previewPushBatch({
        local_dir: localDir.trim(),
        serials: selectedSerials.length ? selectedSerials : undefined,
      });
      appendLog(
        `批量预览：${preview.pair_count ?? 0} 对配对（文件 ${preview.file_count} / 设备 ${preview.device_count}）`
      );
      const res = await pushBatch({
        local_dir: localDir.trim(),
        remote_dir: remoteDir.trim() || "/sdcard/Download",
        serials: selectedSerials.length ? selectedSerials : undefined,
      });
      for (const r of res.results || []) {
        appendLog(
          r.ok
            ? `${r.adb_serial}: 已推送 ${r.file} → ${r.remote}`
            : `${r.adb_serial}: 推送失败 ${r.file} — ${r.error || "未知"}`
        );
      }
      appendLog(`批量推送完成：成功 ${res.success ?? 0}，失败 ${res.fail ?? 0}`);
    } catch (e) {
      appendLog(`批量推送失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setPushing(false);
    }
  };

  const handlePushFile = async () => {
    if (!localFile.trim()) {
      appendLog("请填写本地文件路径");
      return;
    }
    if (!selectedSerials.length) {
      appendLog("请至少选择一台设备");
      return;
    }
    setPushing(true);
    try {
      const res = await pushFile({
        local_file: localFile.trim(),
        remote_dir: remoteDir.trim() || "/sdcard/Download",
        serials: selectedSerials,
      });
      for (const r of res.results || []) {
        appendLog(
          r.ok
            ? `${r.adb_serial}: 已替换 ${r.file}`
            : `${r.adb_serial}: 替换失败 — ${r.error || "未知"}`
        );
      }
      appendLog(`单文件推送完成：成功 ${res.success ?? 0}，失败 ${res.fail ?? 0}`);
    } catch (e) {
      appendLog(`单文件推送失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setPushing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Master 地址 */}
      <Card className="border-glow bg-bg-card/80 backdrop-blur-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-white">
            <Rocket className="w-5 h-5 text-accent" />
            Master 与 Agent 配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-muted-foreground">推荐 Master URL</span>
            <code className="flex-1 min-w-[200px] px-3 py-2 rounded-lg bg-black/40 border border-accent/10 text-accent text-sm">
              {masterUrl || (masterErr ? "—" : "加载中…")}
            </code>
            <button
              type="button"
              onClick={handleCopyMaster}
              disabled={!masterUrl}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 text-sm disabled:opacity-40"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              复制
            </button>
            <button
              type="button"
              onClick={() => {
                refreshDevices();
                refreshAgents();
              }}
              disabled={loadingDevices}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-accent/20 text-white hover:bg-accent/10 text-sm"
            >
              {loadingDevices ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              刷新设备
            </button>
            <button
              type="button"
              onClick={handleDeploy}
              disabled={deploying || loadingDevices}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-black font-medium hover:bg-accent/90 text-sm disabled:opacity-50"
            >
              {deploying ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Rocket className="w-4 h-4" />
              )}
              批量下发配置
            </button>
          </div>
          {masterErr && (
            <p className="text-sm text-red-400">{masterErr}</p>
          )}
          {deviceErr && (
            <p className="text-sm text-red-400">{deviceErr}</p>
          )}

          <details className="rounded-lg border border-accent/10 bg-black/20 p-3">
            <summary className="cursor-pointer text-sm text-muted-foreground select-none">
              可选：同时安装 APK
            </summary>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-white">
                <input
                  type="checkbox"
                  checked={installApk}
                  onChange={(e) => setInstallApk(e.target.checked)}
                  className="rounded border-accent/30"
                />
                安装后再下发配置
              </label>
              <input
                type="text"
                value={apkPath}
                onChange={(e) => setApkPath(e.target.value)}
                disabled={!installApk}
                placeholder="agent-bundle/app-release.apk"
                className="flex-1 min-w-[240px] px-3 py-2 rounded-lg bg-black/40 border border-accent/10 text-sm text-white disabled:opacity-40"
              />
            </div>
          </details>

          <div className="overflow-x-auto rounded-lg border border-accent/10">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-accent/10 text-muted-foreground text-left">
                  <th className="p-3 w-10">
                    <input
                      type="checkbox"
                      checked={
                        devices.filter((d) => d.state === "device").length > 0 &&
                        selected.size ===
                          devices.filter((d) => d.state === "device").length
                      }
                      onChange={toggleAll}
                      aria-label="全选"
                    />
                  </th>
                  <th className="p-3">ADB Serial</th>
                  <th className="p-3">型号</th>
                  <th className="p-3">Agent Serial</th>
                  <th className="p-3">在线 Agent</th>
                  <th className="p-3">状态</th>
                </tr>
              </thead>
              <tbody>
                {devices.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-muted-foreground">
                      {loadingDevices ? "正在扫描 ADB…" : "暂无设备，请确认 adb devices 可见后刷新"}
                    </td>
                  </tr>
                ) : (
                  devices.map((d) => {
                    const agentSerial =
                      d.agent_serial || agentSerialPreview(d.adb_serial);
                    const online = onlineAgentSerials.has(agentSerial);
                    const isDevice = d.state === "device";
                    return (
                      <tr
                        key={d.adb_serial}
                        className="border-b border-accent/5 hover:bg-accent/5"
                      >
                        <td className="p-3">
                          <input
                            type="checkbox"
                            checked={selected.has(d.adb_serial)}
                            onChange={() => toggleSelect(d.adb_serial)}
                            disabled={!isDevice}
                          />
                        </td>
                        <td className="p-3 font-mono text-white">{d.adb_serial}</td>
                        <td className="p-3 text-muted-foreground">{d.model || "—"}</td>
                        <td className="p-3 font-mono text-accent/90">{agentSerial}</td>
                        <td className="p-3">
                          {online ? (
                            <span className="inline-flex items-center gap-1 text-neon-green">
                              <Wifi className="w-4 h-4" /> 已连接
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-muted-foreground">
                              <WifiOff className="w-4 h-4" /> 未连接
                            </span>
                          )}
                        </td>
                        <td className="p-3">
                          <span
                            className={
                              isDevice ? "text-neon-green" : "text-yellow-500/80"
                            }
                          >
                            {d.state}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 文件推送 */}
      <Card className="border-glow bg-bg-card/80 backdrop-blur-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-white">
            <Upload className="w-5 h-5 text-accent" />
            文件推送（Master 宿主机路径）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-muted-foreground">
            路径填写在运行 Master 的机器上可访问的本地路径（如 Windows 雷电环境）。
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="block space-y-1">
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                <FolderOpen className="w-4 h-4" /> 本地文件夹（批量 1:1）
              </span>
              <input
                type="text"
                value={localDir}
                onChange={(e) => setLocalDir(e.target.value)}
                placeholder="D:\push\batch"
                className="w-full px-3 py-2 rounded-lg bg-black/40 border border-accent/10 text-white text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-sm text-muted-foreground">本地单文件（替换推送）</span>
              <input
                type="text"
                value={localFile}
                onChange={(e) => setLocalFile(e.target.value)}
                placeholder="D:\push\one.apk"
                className="w-full px-3 py-2 rounded-lg bg-black/40 border border-accent/10 text-white text-sm"
              />
            </label>
            <label className="block space-y-1 md:col-span-2">
              <span className="text-sm text-muted-foreground">模拟器目标目录</span>
              <input
                type="text"
                value={remoteDir}
                onChange={(e) => setRemoteDir(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-black/40 border border-accent/10 text-white text-sm"
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handlePushBatch}
              disabled={pushing}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-accent/30 text-white hover:bg-accent/10 text-sm disabled:opacity-50"
            >
              {pushing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              批量分配推送
            </button>
            <button
              type="button"
              onClick={handlePushFile}
              disabled={pushing}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-accent/30 text-white hover:bg-accent/10 text-sm disabled:opacity-50"
            >
              单文件替换（选中设备）
            </button>
          </div>
        </CardContent>
      </Card>

      {/* 部署结果与日志 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-glow bg-bg-card/80 backdrop-blur-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-white text-base">最近下发结果</CardTitle>
          </CardHeader>
          <CardContent>
            {deployResults.length === 0 ? (
              <p className="text-sm text-muted-foreground">下发配置后在此显示每台设备结果</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {deployResults.map((r) => (
                  <li
                    key={r.adb_serial}
                    className={`flex items-start gap-2 ${r.ok ? "text-neon-green" : "text-red-400"}`}
                  >
                    {r.ok ? <Check className="w-4 h-4 shrink-0 mt-0.5" /> : null}
                    <span>
                      <span className="font-mono">{r.adb_serial}</span>
                      {r.agent_serial ? ` → ${r.agent_serial}` : ""}
                      {!r.ok && r.error ? ` — ${r.error}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="border-glow bg-bg-card/80 backdrop-blur-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-white text-base">操作日志</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48 overflow-y-auto rounded-lg bg-black/40 border border-accent/10 p-3 font-mono text-xs text-muted-foreground space-y-1">
              {logs.length === 0 ? (
                <p className="text-muted-foreground">暂无日志</p>
              ) : (
                logs.map((line, i) => (
                  <div key={`${i}-${line.slice(0, 24)}`} className="text-white/80">
                    {line}
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

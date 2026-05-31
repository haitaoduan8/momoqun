/**
 * momoqun API 服务层
 * 连接后端 FastAPI 服务器 (http://localhost:5100)
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5100";

// 通用请求方法
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// ============ ADB 设备管理 ============

export interface AdbDevice {
  serial: string;
  state: string;
  info: string;
}

export async function getAdbDevices(): Promise<{ devices: AdbDevice[] }> {
  return fetchAPI("/api/adb/devices");
}

export async function connectAdb(address: string): Promise<{ ok: boolean; error?: string }> {
  return fetchAPI("/api/adb/connect", {
    method: "POST",
    body: JSON.stringify({ address }),
  });
}

export async function disconnectAdb(address: string): Promise<{ ok: boolean; error?: string }> {
  return fetchAPI("/api/adb/disconnect", {
    method: "POST",
    body: JSON.stringify({ address }),
  });
}

export async function initAdb(serial: string): Promise<{ ok: boolean; error?: string }> {
  return fetchAPI("/api/adb/init", {
    method: "POST",
    body: JSON.stringify({ serial }),
  });
}

// ============ 设备管理 ============

export interface Device {
  serial: string;
  name: string;
  state: "running" | "paused" | "stopped" | "error";
  round_number?: number;
  friends_total?: number;
  friends_this_round?: number;
}

export async function getDevices(): Promise<Device[]> {
  return fetchAPI("/api/devices");
}

export async function addDevice(serial: string, name?: string): Promise<{ ok: boolean; error?: string }> {
  return fetchAPI("/api/devices/add", {
    method: "POST",
    body: JSON.stringify({ serial, name: name || serial }),
  });
}

export async function removeDevice(serial: string): Promise<{ ok: boolean; error?: string }> {
  return fetchAPI("/api/devices/remove", {
    method: "POST",
    body: JSON.stringify({ serial }),
  });
}

export async function deviceAction(
  action: "start" | "stop" | "pause" | "resume",
  serial: string
): Promise<{ ok: boolean; error?: string }> {
  return fetchAPI(`/api/devices/${action}`, {
    method: "POST",
    body: JSON.stringify({ serial }),
  });
}

// ============ 统计数据 ============
// 对应后端 /api/stats 返回结构

export interface Stats {
  friends: Record<string, number>;
  round_number: number;
  friends_this_round: number;
  device_count: number;
}

export async function getStats(): Promise<Stats> {
  return fetchAPI("/api/stats");
}

// ============ 运行日志 ============

export interface LogEntry {
  time: string;
  level: string;
  name: string;
  message: string;
}

export async function getLogs(limit = 200): Promise<{ logs: LogEntry[] }> {
  return fetchAPI(`/api/logs?limit=${limit}`);
}

// ============ 配置管理 ============

export interface Config {
  group_name: string;
  chat_rounds_before_follow: number;
  max_chat_rounds: number;
  round_end_wait_s: number;
  chat_round_wait_s: number;
  greet_scan_interval_s: number;
  invite_back_message: string;
  max_consecutive_errors: number;
  huiguan_message_round: number;
  huiguan_enabled: boolean;
  direct_group_mode: boolean;
  reply_interval: { min: number; max: number };
  chat_strategy: string;
  message_pools: Array<{ id: number; messages: string[] }>;
}

export async function getConfig(): Promise<Config> {
  return fetchAPI("/api/config");
}

export async function updateConfig(config: Partial<Config>): Promise<{ ok: boolean; error?: string }> {
  return fetchAPI("/api/config", {
    method: "PUT",
    body: JSON.stringify({ config }),
  });
}

// ============ 账号检测 ============

export interface AccountCheckStatus {
  config: {
    enabled: boolean;
    interval_minutes: number;
  };
  devices: Array<{
    serial: string;
    account_status: "ok" | "abnormal" | "unknown" | "error";
    last_check_at?: number;
  }>;
}

export async function getAccountCheckStatus(): Promise<AccountCheckStatus> {
  return fetchAPI("/api/account-check/status");
}

export async function updateAccountCheckConfig(body: {
  enabled?: boolean;
  interval_minutes?: number;
}): Promise<{ ok: boolean; config?: any }> {
  return fetchAPI("/api/account-check/config", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function triggerAccountCheck(): Promise<{ ok: boolean; triggered?: number }> {
  return fetchAPI("/api/account-check/trigger", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function dismissAccountCheck(serial: string): Promise<{ ok: boolean }> {
  return fetchAPI("/api/account-check/dismiss", {
    method: "POST",
    body: JSON.stringify({ serial }),
  });
}

// ============ 系统控制 ============

export async function shutdown(): Promise<{ ok: boolean; message?: string }> {
  return fetchAPI("/api/shutdown", {
    method: "POST",
  });
}

/**
 * momoqun API 服务层
 * 连接后端 FastAPI 服务器 (http://localhost:5100)
 */

import { authHeaders } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export class ApiAuthError extends Error {
  constructor(message = "未授权") {
    super(message);
    this.name = "ApiAuthError";
  }
}

// 通用请求方法
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options?.headers,
    },
  });

  if (response.status === 401) {
    throw new ApiAuthError();
  }

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// ============ 鉴权 ============

export interface AuthStatus {
  auth_required: boolean;
  shell_exec_allowed: boolean;
  heartbeat_timeout_sec: number;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const url = `${API_BASE}/api/auth/status`;
  const response = await fetch(url);
  if (response.ok) {
    return response.json();
  }
  // 旧版 server 无此路由：从 master-address 读取鉴权状态，或视为未启用
  if (response.status === 404) {
    const fallback = await fetch(`${API_BASE}/api/master-address`);
    if (fallback.ok) {
      const data = await fallback.json();
      return {
        auth_required: Boolean(data.auth_required),
        shell_exec_allowed: Boolean(data.shell_exec_allowed),
        heartbeat_timeout_sec: Number(data.heartbeat_timeout_sec) || 30,
      };
    }
  }
  throw new Error(`API Error: ${response.status}`);
}

// ============ Master 地址（路线 C：下发给模拟器 Agent） ============

export interface MasterAddress {
  addresses: string[];
  port: number;
  ws_urls: string[];
  auth_required?: boolean;
  api_token?: string;
}

export async function getMasterAddress(): Promise<MasterAddress> {
  return fetchAPI("/api/master-address");
}

// ============ 在线 Agent（路线 C WebSocket） ============

export interface OnlineAgent {
  serial: string;
  connected_for_s: number;
  idle_for_s: number;
  pending_rpc: number;
}

export async function getAgents(): Promise<{ agents: OnlineAgent[] }> {
  return fetchAPI("/api/agents");
}

// ============ 设备管理 ============

export interface Device {
  serial: string;
  name: string;
  state: "running" | "paused" | "stopped" | "error" | "waiting_agent";
  round_number?: number;
  friends_total?: number;
  friends_this_round?: number;
  error?: string | null;
  current_phase?: string;
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
  action: "start" | "stop" | "pause" | "resume" | "start_all" | "pause_all",
  serial?: string
): Promise<{ ok: boolean; error?: string; started?: number }> {
  return fetchAPI(`/api/devices/${action}`, {
    method: "POST",
    body: JSON.stringify(serial ? { serial } : {}),
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

// ============ 聚合 Dashboard（设备 + 统计 + 账号检测 + Agent） ============

export interface DashboardResponse {
  devices: Device[];
  stats: Stats;
  account_check: AccountCheckStatus;
  agents: OnlineAgent[];
}

export async function getDashboard(): Promise<DashboardResponse> {
  return fetchAPI("/api/dashboard");
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
  chat_ignore_names?: string[];
  message_pools: Array<{ id: number; messages: string[] }>;
  security?: {
    api_token?: string;
    allow_shell_exec?: boolean;
    heartbeat_timeout_sec?: number;
  };
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

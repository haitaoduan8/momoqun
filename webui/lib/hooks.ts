'use client';

import { useState, useEffect, useCallback } from "react";
import {
  getDevices,
  getStats,
  getAccountCheckStatus,
  getConfig,
  type Device,
  type Stats,
  type AccountCheckStatus,
  type Config,
} from "./api";

// ============ 设备轮询 Hook ============

export function useDevices(interval = 3000) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDevices = useCallback(async () => {
    try {
      const data = await getDevices();
      setDevices(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取设备失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDevices();
    const timer = setInterval(fetchDevices, interval);
    return () => clearInterval(timer);
  }, [fetchDevices, interval]);

  return { devices, loading, error, refresh: fetchDevices };
}

// ============ 统计数据 Hook ============

export function useStats(interval = 5000) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      console.error("获取统计数据失败:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const timer = setInterval(fetchStats, interval);
    return () => clearInterval(timer);
  }, [fetchStats, interval]);

  return { stats, loading, refresh: fetchStats };
}

// ============ 账号检测 Hook ============

export function useAccountCheck(interval = 3000) {
  const [status, setStatus] = useState<AccountCheckStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getAccountCheckStatus();
      setStatus(data);
    } catch (err) {
      console.error("获取账号检测状态失败:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, interval);
    return () => clearInterval(timer);
  }, [fetchStatus, interval]);

  return { status, loading, refresh: fetchStatus };
}

// ============ 配置 Hook ============

export function useConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchConfig = useCallback(async () => {
    try {
      const data = await getConfig();
      setConfig(data);
    } catch (err) {
      console.error("获取配置失败:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  return { config, loading, refresh: fetchConfig };
}

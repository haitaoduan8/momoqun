'use client';

import { useCallback, useEffect, useState } from "react";
import { getAuthStatus } from "@/lib/api";
import { clearStoredToken, getStoredToken, setStoredToken } from "@/lib/auth";
import { Loader2, KeyRound } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function probeToken(token: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/devices`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) return false;
  return res.ok;
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<"loading" | "login" | "ready">("loading");
  const [tokenInput, setTokenInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const bootstrap = useCallback(async () => {
    setPhase("loading");
    setError(null);
    try {
      const status = await getAuthStatus();
      if (!status.auth_required) {
        setPhase("ready");
        return;
      }
      const stored = getStoredToken();
      if (!stored) {
        setPhase("login");
        return;
      }
      const ok = await probeToken(stored);
      if (!ok) {
        clearStoredToken();
        setPhase("login");
        setError("Token 无效或已过期，请重新输入");
        return;
      }
      setPhase("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "无法连接后端");
      setPhase("login");
    }
  }, []);

  useEffect(() => {
    setTokenInput(getStoredToken());
    bootstrap();
  }, [bootstrap]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = tokenInput.trim();
    if (!t) {
      setError("请输入 API Token");
      return;
    }
    const ok = await probeToken(t);
    if (!ok) {
      setError("Token 无效");
      return;
    }
    setStoredToken(t);
    setError(null);
    setPhase("ready");
  };

  if (phase === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  if (phase === "login") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black p-6">
        <form
          onSubmit={handleSubmit}
          className="w-full max-w-md rounded-xl border border-accent/20 bg-bg-card p-8 space-y-4"
        >
          <div className="flex items-center gap-3">
            <KeyRound className="w-6 h-6 text-accent" />
            <h1 className="text-lg font-semibold text-white">需要 API Token</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            与 <span className="font-mono">config/settings.yaml</span> 中{" "}
            <span className="font-mono">security.api_token</span> 保持一致。
          </p>
          <input
            type="password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="输入 API Token"
            className="w-full rounded-lg bg-black/40 border border-accent/20 px-3 py-2 text-sm text-white"
            autoComplete="off"
          />
          {error && <p className="text-sm text-neon-red">{error}</p>}
          <button
            type="submit"
            className="w-full py-2 rounded-lg bg-accent text-black font-medium hover:opacity-90"
          >
            进入控制台
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}

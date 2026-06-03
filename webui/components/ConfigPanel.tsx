'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfig } from "@/lib/hooks";
import { updateConfig, type Config } from "@/lib/api";
import {
  Settings,
  Save,
  Loader2,
  MessageSquare,
  Clock,
  Zap,
  Shield,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { useState, useEffect } from "react";

type FormState = {
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
  reply_interval_min: number;
  reply_interval_max: number;
  chat_ignore_names_text: string;
  api_token: string;
  allow_shell_exec: boolean;
  heartbeat_timeout_sec: number;
  message_pools: Array<{ id: number; messages: string[] }>;
};

function configToForm(config: Config): FormState {
  return {
    group_name: config.group_name || "",
    chat_rounds_before_follow: config.chat_rounds_before_follow || 3,
    max_chat_rounds: config.max_chat_rounds || 10,
    round_end_wait_s: config.round_end_wait_s || 10,
    chat_round_wait_s: config.chat_round_wait_s || 30,
    greet_scan_interval_s: config.greet_scan_interval_s || 5,
    invite_back_message: config.invite_back_message || "",
    max_consecutive_errors: config.max_consecutive_errors || 5,
    huiguan_message_round: config.huiguan_message_round || 3,
    huiguan_enabled: config.huiguan_enabled || false,
    direct_group_mode: config.direct_group_mode ?? false,
    reply_interval_min: config.reply_interval?.min ?? 1,
    reply_interval_max: config.reply_interval?.max ?? 3,
    chat_ignore_names_text: (config.chat_ignore_names || []).join("\n"),
    api_token: config.security?.api_token || "",
    allow_shell_exec: config.security?.allow_shell_exec ?? false,
    heartbeat_timeout_sec: config.security?.heartbeat_timeout_sec ?? 30,
    message_pools: (config.message_pools || []).map((p) => ({
      id: p.id,
      messages: [...(p.messages || [])],
    })),
  };
}

function formToPatch(form: FormState): Partial<Config> {
  const ignoreNames = form.chat_ignore_names_text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);

  return {
    group_name: form.group_name,
    chat_rounds_before_follow: form.chat_rounds_before_follow,
    max_chat_rounds: form.max_chat_rounds,
    round_end_wait_s: form.round_end_wait_s,
    chat_round_wait_s: form.chat_round_wait_s,
    greet_scan_interval_s: form.greet_scan_interval_s,
    invite_back_message: form.invite_back_message,
    max_consecutive_errors: form.max_consecutive_errors,
    huiguan_message_round: form.huiguan_message_round,
    huiguan_enabled: form.huiguan_enabled,
    direct_group_mode: form.direct_group_mode,
    reply_interval: {
      min: form.reply_interval_min,
      max: form.reply_interval_max,
    },
    chat_ignore_names: ignoreNames,
    message_pools: form.message_pools.map((p) => ({
      id: p.id,
      messages: p.messages.filter((m) => m.trim()),
    })),
    security: {
      api_token: form.api_token,
      allow_shell_exec: form.allow_shell_exec,
      heartbeat_timeout_sec: form.heartbeat_timeout_sec,
    },
  };
}

export function ConfigPanel() {
  const { config, loading, refresh } = useConfig();
  const [formData, setFormData] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    if (config) {
      setFormData(configToForm(config));
    }
  }, [config]);

  const handleSave = async () => {
    if (!formData) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const result = await updateConfig(formToPatch(formData));
      if (result.ok) {
        setSaveMessage({ type: "success", text: "配置已保存并热更新" });
        await refresh();
      } else {
        setSaveMessage({ type: "error", text: result.error || "保存失败" });
      }
    } catch (err) {
      setSaveMessage({
        type: "error",
        text: err instanceof Error ? err.message : "保存失败",
      });
    } finally {
      setSaving(false);
    }
  };

  const updatePoolMessage = (poolIndex: number, msgIndex: number, value: string) => {
    if (!formData) return;
    const pools = formData.message_pools.map((p, pi) =>
      pi === poolIndex
        ? {
            ...p,
            messages: p.messages.map((m, mi) => (mi === msgIndex ? value : m)),
          }
        : p
    );
    setFormData({ ...formData, message_pools: pools });
  };

  const addPoolMessage = (poolIndex: number) => {
    if (!formData) return;
    const pools = formData.message_pools.map((p, pi) =>
      pi === poolIndex ? { ...p, messages: [...p.messages, ""] } : p
    );
    setFormData({ ...formData, message_pools: pools });
  };

  const removePoolMessage = (poolIndex: number, msgIndex: number) => {
    if (!formData) return;
    const pools = formData.message_pools.map((p, pi) =>
      pi === poolIndex
        ? { ...p, messages: p.messages.filter((_, mi) => mi !== msgIndex) }
        : p
    );
    setFormData({ ...formData, message_pools: pools });
  };

  if (loading || !formData) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {saveMessage && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
            saveMessage.type === "success"
              ? "bg-neon-green/10 text-neon-green border border-neon-green/20"
              : "bg-neon-red/10 text-neon-red border border-neon-red/20"
          }`}
        >
          {saveMessage.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          {saveMessage.text}
        </div>
      )}

      {/* 安全设置 */}
      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-accent" />
            安全与 Agent
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm text-muted-foreground">API Token（留空关闭鉴权）</label>
            <input
              type="password"
              value={formData.api_token}
              onChange={(e) => setFormData({ ...formData, api_token: e.target.value })}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30 font-mono"
              placeholder="与 Agent / Web UI 使用相同令牌"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">心跳超时（秒）</label>
              <input
                type="number"
                value={formData.heartbeat_timeout_sec}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    heartbeat_timeout_sec: parseInt(e.target.value, 10) || 30,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div className="flex items-end">
              <div className="flex items-center justify-between w-full p-4 rounded-lg bg-bg-card border border-accent/6">
                <div>
                  <p className="font-medium text-white text-sm">允许 shell_exec</p>
                  <p className="text-xs text-muted-foreground">Agent 反向执行 adb shell</p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setFormData({
                      ...formData,
                      allow_shell_exec: !formData.allow_shell_exec,
                    })
                  }
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    formData.allow_shell_exec ? "bg-neon-red" : "bg-gray-600"
                  }`}
                >
                  <div
                    className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                      formData.allow_shell_exec ? "translate-x-7" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 群聊设置 */}
      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-accent" />
            群聊设置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm text-muted-foreground">群聊名称</label>
            <input
              type="text"
              value={formData.group_name}
              onChange={(e) => setFormData({ ...formData, group_name: e.target.value })}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              placeholder="输入群聊名称"
            />
          </div>
          <div>
            <label className="text-sm text-muted-foreground">回关邀请话术</label>
            <input
              type="text"
              value={formData.invite_back_message}
              onChange={(e) =>
                setFormData({ ...formData, invite_back_message: e.target.value })
              }
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              placeholder="输入邀请话术"
            />
          </div>
          <div>
            <label className="text-sm text-muted-foreground">聊天忽略名称（每行一个）</label>
            <textarea
              value={formData.chat_ignore_names_text}
              onChange={(e) =>
                setFormData({ ...formData, chat_ignore_names_text: e.target.value })
              }
              rows={5}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30 font-mono text-sm"
              placeholder="收到的招呼&#10;互动通知"
            />
          </div>
        </CardContent>
      </Card>

      {/* 直接拉群模式 */}
      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-accent" />
            运行模式
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 rounded-lg bg-bg-card border border-accent/6">
            <div>
              <p className="font-medium text-white">直接拉群模式</p>
              <p className="text-sm text-muted-foreground">
                开启后仅通过招呼→邀请进群→拉黑，跳过聊天和关注环节
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                setFormData({
                  ...formData,
                  direct_group_mode: !formData.direct_group_mode,
                })
              }
              className={`relative w-12 h-6 rounded-full transition-colors ${
                formData.direct_group_mode ? "bg-accent" : "bg-gray-600"
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  formData.direct_group_mode ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* 回关邀请设置 */}
      <Card
        className={`border-glow ${formData.direct_group_mode ? "opacity-50 pointer-events-none" : ""}`}
      >
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-accent" />
            回关邀请设置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 rounded-lg bg-bg-card border border-accent/6">
            <div>
              <p className="font-medium text-white">发送回关邀请话术</p>
              <p className="text-sm text-muted-foreground">
                开启后达到指定轮数发送回关邀请，关闭后正常按消息池对话
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                setFormData({ ...formData, huiguan_enabled: !formData.huiguan_enabled })
              }
              className={`relative w-12 h-6 rounded-full transition-colors ${
                formData.huiguan_enabled ? "bg-accent" : "bg-gray-600"
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  formData.huiguan_enabled ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">第几轮发送回关邀请</label>
            <input
              type="number"
              value={formData.huiguan_message_round}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  huiguan_message_round: parseInt(e.target.value, 10) || 0,
                })
              }
              disabled={!formData.huiguan_enabled}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30 disabled:opacity-50"
            />
          </div>
        </CardContent>
      </Card>

      {/* 消息池 */}
      <Card
        className={`border-glow ${formData.direct_group_mode ? "opacity-50 pointer-events-none" : ""}`}
      >
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-accent" />
            消息池
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {formData.message_pools.map((pool, poolIndex) => (
            <div
              key={pool.id}
              className="p-4 rounded-lg bg-bg-card border border-accent/6 space-y-2"
            >
              <p className="text-sm font-medium text-white">第 {pool.id} 轮话术</p>
              {pool.messages.map((msg, msgIndex) => (
                <div key={msgIndex} className="flex gap-2">
                  <input
                    type="text"
                    value={msg}
                    onChange={(e) => updatePoolMessage(poolIndex, msgIndex, e.target.value)}
                    className="flex-1 px-3 py-2 bg-bg-input border border-accent/6 rounded-lg text-white text-sm focus:outline-none focus:border-accent/30"
                  />
                  <button
                    type="button"
                    onClick={() => removePoolMessage(poolIndex, msgIndex)}
                    className="p-2 text-neon-red hover:bg-neon-red/10 rounded-lg"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => addPoolMessage(poolIndex)}
                className="flex items-center gap-1 text-xs text-accent hover:underline"
              >
                <Plus className="w-3 h-3" />
                添加话术
              </button>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* 聊天参数 */}
      <Card
        className={`border-glow ${formData.direct_group_mode ? "opacity-50 pointer-events-none" : ""}`}
      >
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-accent" />
            聊天参数
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">聊N轮后关注</label>
              <input
                type="number"
                value={formData.chat_rounds_before_follow}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    chat_rounds_before_follow: parseInt(e.target.value, 10) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">最大聊天轮数</label>
              <input
                type="number"
                value={formData.max_chat_rounds}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    max_chat_rounds: parseInt(e.target.value, 10) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">最大连续错误</label>
              <input
                type="number"
                value={formData.max_consecutive_errors}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    max_consecutive_errors: parseInt(e.target.value, 10) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">回复间隔最小（秒）</label>
              <input
                type="number"
                step="0.1"
                value={formData.reply_interval_min}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    reply_interval_min: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">回复间隔最大（秒）</label>
              <input
                type="number"
                step="0.1"
                value={formData.reply_interval_max}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    reply_interval_max: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 时间参数 */}
      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-accent" />
            时间参数
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">轮次间隔(秒)</label>
              <input
                type="number"
                value={formData.round_end_wait_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    round_end_wait_s: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">回复等待(秒)</label>
              <input
                type="number"
                value={formData.chat_round_wait_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    chat_round_wait_s: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">招呼扫描间隔(秒)</label>
              <input
                type="number"
                value={formData.greet_scan_interval_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    greet_scan_interval_s: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-accent text-black font-semibold rounded-lg hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          保存配置
        </button>
      </div>
    </div>
  );
}

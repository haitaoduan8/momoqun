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
  Shield,
  CheckCircle2,
  AlertCircle,
  Rocket,
} from "lucide-react";
import { useState, useEffect } from "react";
import { LowGreetPanel } from "@/components/LowGreetPanel";

type FormState = {
  group_name: string;
  round_end_wait_s: number;
  greet_scan_interval_s: number;
  max_consecutive_errors: number;
  chat_ignore_names_text: string;
  account_boot_enabled: boolean;
  preset_address: string;
  dynamic_content: string;
  post_dynamic_enabled: boolean;
  account_boot_step_wait_s: number;
  page_verify_retries: number;
  page_verify_poll_s: number;
  post_click_stable_s: number;
  allow_coord_fallback: boolean;
  clone_select_wait_s: number;
  post_publish_wait_s: number;
  first_batch_min_count: number;
  low_greet_wait_minutes: number;
  api_token: string;
  allow_shell_exec: boolean;
  heartbeat_timeout_sec: number;
};

function configToForm(config: Config): FormState {
  const boot = config.account_boot || {};
  const greet = config.approve_greeting || {};
  return {
    group_name: config.group_name || "",
    round_end_wait_s: config.round_end_wait_s || 10,
    greet_scan_interval_s: config.greet_scan_interval_s || 5,
    max_consecutive_errors: config.max_consecutive_errors || 5,
    chat_ignore_names_text: (config.chat_ignore_names || []).join("\n"),
    account_boot_enabled: boot.enabled ?? true,
    preset_address: boot.preset_address || "",
    dynamic_content: boot.dynamic_content || "",
    post_dynamic_enabled: boot.post_dynamic_enabled ?? true,
    account_boot_step_wait_s: boot.step_wait_s ?? 1.5,
    page_verify_retries: boot.page_verify_retries ?? 12,
    page_verify_poll_s: boot.page_verify_poll_s ?? 1.0,
    post_click_stable_s: boot.post_click_stable_s ?? 2.0,
    allow_coord_fallback: boot.allow_coord_fallback ?? true,
    clone_select_wait_s: boot.clone_select_wait_s ?? 2,
    post_publish_wait_s: boot.post_publish_wait_s ?? 2,
    first_batch_min_count: greet.first_batch_min_count ?? 3,
    low_greet_wait_minutes: greet.low_greet_wait_minutes ?? 5,
    api_token: config.security?.api_token || "",
    allow_shell_exec: config.security?.allow_shell_exec ?? false,
    heartbeat_timeout_sec: config.security?.heartbeat_timeout_sec ?? 30,
  };
}

function formToPatch(form: FormState): Partial<Config> {
  const ignoreNames = form.chat_ignore_names_text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);

  return {
    group_name: form.group_name,
    round_end_wait_s: form.round_end_wait_s,
    greet_scan_interval_s: form.greet_scan_interval_s,
    max_consecutive_errors: form.max_consecutive_errors,
    chat_ignore_names: ignoreNames,
    account_boot: {
      enabled: form.account_boot_enabled,
      preset_address: form.preset_address.trim(),
      dynamic_content: form.dynamic_content.trim(),
      post_dynamic_enabled: form.post_dynamic_enabled,
      step_wait_s: form.account_boot_step_wait_s,
      page_verify_retries: form.page_verify_retries,
      page_verify_poll_s: form.page_verify_poll_s,
      post_click_stable_s: form.post_click_stable_s,
      allow_coord_fallback: form.allow_coord_fallback,
      clone_select_wait_s: form.clone_select_wait_s,
      post_publish_wait_s: form.post_publish_wait_s,
    },
    approve_greeting: {
      first_batch_min_count: form.first_batch_min_count,
      low_greet_wait_minutes: form.low_greet_wait_minutes,
    },
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

      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rocket className="w-5 h-5 text-accent" />
            自动上号
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            设备启动时执行一次（假定已在桌面）。每一步点击前 dump 并校验页面，通过后才点击；任一步点击失败（含重试耗尽）会立即暂停设备，并在控制台显示「上号失败 [步骤]: 原因」，不会继续发动态或招呼。含拖走红点；账号异常换号后会自动重新上号。
          </p>
          <div className="p-3 rounded-lg bg-accent/5 border border-accent/10 text-xs text-muted-foreground space-y-1">
            <p>日志关键字：<span className="text-accent">【点击前 dump】</span> → <span className="text-accent">【页面OK】</span> → <span className="text-accent">【点击】</span> → <span className="text-accent">【点击后等待】</span></p>
            <p>失败时：<span className="text-red-400">【点击失败】</span> / <span className="text-red-400">【元素未找到】</span>，设备卡片会显示暂停原因。</p>
            <p>页面看起来正常却找不到元素，常见原因是控件用 text 显示但配置只写了 contentDesc；现已同时匹配 text/contentDesc。</p>
            <p>页面校验通过但元素仍未命中时，可启用坐标兜底（日志会打 <span className="text-accent">【坐标兜底】</span>）。</p>
          </div>
          <div className="flex items-center justify-between p-4 rounded-lg bg-bg-card border border-accent/6">
            <div>
              <p className="font-medium text-white text-sm">启用自动上号</p>
              <p className="text-xs text-muted-foreground">关闭后启动设备时不会自动上号</p>
            </div>
            <button
              type="button"
              onClick={() =>
                setFormData({
                  ...formData,
                  account_boot_enabled: !formData.account_boot_enabled,
                })
              }
              className={`relative w-12 h-6 rounded-full transition-colors ${
                formData.account_boot_enabled ? "bg-neon-green" : "bg-gray-600"
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  formData.account_boot_enabled ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">预设地址（位置模拟输入）</label>
            <input
              type="text"
              value={formData.preset_address}
              onChange={(e) => setFormData({ ...formData, preset_address: e.target.value })}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              placeholder="例如：济南市历下区泉城路"
            />
          </div>
          <div className="flex items-center justify-between p-4 rounded-lg bg-bg-card border border-accent/6">
            <div>
              <p className="font-medium text-white text-sm">发动态</p>
              <p className="text-xs text-muted-foreground">上号后：更多 → 发动态 → 发布 → 消息</p>
            </div>
            <button
              type="button"
              onClick={() =>
                setFormData({
                  ...formData,
                  post_dynamic_enabled: !formData.post_dynamic_enabled,
                })
              }
              className={`relative w-12 h-6 rounded-full transition-colors ${
                formData.post_dynamic_enabled ? "bg-neon-green" : "bg-gray-600"
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  formData.post_dynamic_enabled ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">动态文案</label>
            <textarea
              value={formData.dynamic_content}
              onChange={(e) => setFormData({ ...formData, dynamic_content: e.target.value })}
              rows={3}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30 text-sm"
              placeholder="发动态时自动填入的文案"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">步骤间隔（秒）</label>
              <input
                type="number"
                step="0.1"
                min="0.5"
                value={formData.account_boot_step_wait_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    account_boot_step_wait_s: parseFloat(e.target.value) || 1.5,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">一键切换后等待（秒）</label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={formData.clone_select_wait_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    clone_select_wait_s: parseFloat(e.target.value) || 2,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
              <p className="text-xs text-muted-foreground mt-1">点文件号 → 弹窗点一键切换后，等待环境切换完成</p>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">发布动态后等待（秒）</label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={formData.post_publish_wait_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    post_publish_wait_s: parseFloat(e.target.value) || 2,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">页面校验重试次数</label>
              <input
                type="number"
                min={1}
                max={30}
                value={formData.page_verify_retries}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    page_verify_retries: parseInt(e.target.value, 10) || 12,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
              <p className="text-xs text-muted-foreground mt-1">每次点击前 dump，未就绪则重试</p>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">页面校验间隔（秒）</label>
              <input
                type="number"
                step="0.1"
                min="0.2"
                value={formData.page_verify_poll_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    page_verify_poll_s: parseFloat(e.target.value) || 1,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">点击后稳定等待（秒）</label>
              <input
                type="number"
                step="0.1"
                min="0.5"
                value={formData.post_click_stable_s}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    post_click_stable_s: parseFloat(e.target.value) || 2,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
              <p className="text-xs text-muted-foreground mt-1">点击完成后 wait_ui_stable 上限</p>
            </div>
          </div>
          <div className="flex items-center justify-between p-4 rounded-lg bg-bg-card border border-accent/6">
            <div>
              <p className="font-medium text-white text-sm">坐标点击兜底</p>
              <p className="text-xs text-muted-foreground">
                页面校验通过、元素未命中时使用 elements 中配置的 x/y 坐标点击
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                setFormData({
                  ...formData,
                  allow_coord_fallback: !formData.allow_coord_fallback,
                })
              }
              className={`relative w-12 h-6 rounded-full transition-colors ${
                formData.allow_coord_fallback ? "bg-neon-green" : "bg-gray-600"
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  formData.allow_coord_fallback ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-accent" />
            拉群设置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            首批：招呼数达阈值 → 全部通过 → 一次性批量邀请进群 → 回消息页监测招呼；之后有招呼即通过并拉群
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">
                首批招呼阈值（仅第一次生效）
              </label>
              <input
                type="number"
                min={1}
                value={formData.first_batch_min_count}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    first_batch_min_count: parseInt(e.target.value, 10) || 1,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
              <p className="text-xs text-muted-foreground mt-1">
                招呼数达到此值才开始通过并拉群
              </p>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">
                低招呼登记等待（分钟）
              </label>
              <input
                type="number"
                min={1}
                value={formData.low_greet_wait_minutes}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    low_greet_wait_minutes: parseFloat(e.target.value) || 5,
                  })
                }
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
              <p className="text-xs text-muted-foreground mt-1">
                发完动态后满此时间仍低于阈值，登记号文件名到下方列表
              </p>
            </div>
          </div>
          <LowGreetPanel />
          <div>
            <label className="text-sm text-muted-foreground">目标群聊名称</label>
            <input
              type="text"
              value={formData.group_name}
              onChange={(e) => setFormData({ ...formData, group_name: e.target.value })}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              placeholder="输入群聊名称"
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

      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-accent" />
            运行参数
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          </div>
        </CardContent>
      </Card>

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

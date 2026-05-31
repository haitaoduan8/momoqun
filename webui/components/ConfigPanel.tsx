'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfig } from "@/lib/hooks";
import { updateConfig } from "@/lib/api";
import { Settings, Save, Loader2, MessageSquare, Clock } from "lucide-react";
import { useState, useEffect } from "react";

export function ConfigPanel() {
  const { config, loading } = useConfig();
  const [formData, setFormData] = useState({
    group_name: "",
    chat_rounds_before_follow: 3,
    max_chat_rounds: 10,
    round_end_wait_s: 10,
    chat_round_wait_s: 30,
    greet_scan_interval_s: 5,
    invite_back_message: "",
    max_consecutive_errors: 5,
    huiguan_message_round: 3,
    huiguan_enabled: false,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (config) {
      setFormData({
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
      });
    }
  }, [config]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateConfig(formData);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
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
              onChange={(e) => setFormData({ ...formData, invite_back_message: e.target.value })}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              placeholder="输入邀请话术"
            />
          </div>
        </CardContent>
      </Card>

      {/* 回关邀请设置 */}
      <Card className="border-glow">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-accent" />
            回关邀请设置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 启用开关 */}
          <div className="flex items-center justify-between p-4 rounded-lg bg-bg-card border border-accent/6">
            <div>
              <p className="font-medium text-white">发送回关邀请话术</p>
              <p className="text-sm text-muted-foreground">
                开启后达到指定轮数发送回关邀请，关闭后正常按消息池对话
              </p>
            </div>
            <button
              onClick={() => setFormData({ ...formData, huiguan_enabled: !formData.huiguan_enabled })}
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

          {/* 第几轮发送 */}
          <div>
            <label className="text-sm text-muted-foreground">第几轮发送回关邀请</label>
            <input
              type="number"
              value={formData.huiguan_message_round}
              onChange={(e) => setFormData({ ...formData, huiguan_message_round: parseInt(e.target.value) || 0 })}
              disabled={!formData.huiguan_enabled}
              className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30 disabled:opacity-50 disabled:cursor-not-allowed"
              placeholder="设置为 0 则不发送"
            />
            <p className="text-xs text-muted-foreground mt-1">
              {formData.huiguan_enabled
                ? `聊天进行到第 ${formData.huiguan_message_round} 轮时发送回关邀请话术`
                : "关闭状态：正常按消息池对话，不发送回关邀请"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 聊天参数 */}
      <Card className="border-glow">
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
                onChange={(e) => setFormData({ ...formData, chat_rounds_before_follow: parseInt(e.target.value) || 0 })}
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">最大聊天轮数</label>
              <input
                type="number"
                value={formData.max_chat_rounds}
                onChange={(e) => setFormData({ ...formData, max_chat_rounds: parseInt(e.target.value) || 0 })}
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">最大连续错误</label>
              <input
                type="number"
                value={formData.max_consecutive_errors}
                onChange={(e) => setFormData({ ...formData, max_consecutive_errors: parseInt(e.target.value) || 0 })}
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
                onChange={(e) => setFormData({ ...formData, round_end_wait_s: parseFloat(e.target.value) || 0 })}
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">回复等待(秒)</label>
              <input
                type="number"
                value={formData.chat_round_wait_s}
                onChange={(e) => setFormData({ ...formData, chat_round_wait_s: parseFloat(e.target.value) || 0 })}
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">招呼扫描间隔(秒)</label>
              <input
                type="number"
                value={formData.greet_scan_interval_s}
                onChange={(e) => setFormData({ ...formData, greet_scan_interval_s: parseFloat(e.target.value) || 0 })}
                className="w-full mt-1 px-4 py-2 bg-bg-input border border-accent/6 rounded-lg text-white focus:outline-none focus:border-accent/30"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 保存按钮 */}
      <div className="flex justify-end">
        <button
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

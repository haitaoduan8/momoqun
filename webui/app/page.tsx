'use client';

import { SplineRobot } from "@/components/SplineRobot";
import { Dashboard } from "@/components/Dashboard";
import { LogArea } from "@/components/LogArea";
import { AdbPanel } from "@/components/AdbPanel";
import { ConfigPanel } from "@/components/ConfigPanel";
import { AccountCheckPanel } from "@/components/AccountCheckPanel";
import { Card, CardContent } from "@/components/ui/card";
import {
  Smartphone,
  Settings,
  Shield,
  LogOut,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { shutdown } from "@/lib/api";

// 页面类型
type PageType = "devices" | "config" | "account";

// Logo 组件
function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center shadow-lg shadow-accent/20">
        <span className="text-black font-bold text-lg">M</span>
      </div>
      <span className="text-xl font-bold text-white">momoqun</span>
    </div>
  );
}

// 侧边栏
function Sidebar({
  isOpen,
  onClose,
  isCollapsed,
  onToggleCollapse,
  activePage,
  onPageChange,
}: {
  isOpen: boolean;
  onClose: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  activePage: PageType;
  onPageChange: (page: PageType) => void;
}) {
  const menuItems = [
    { icon: Smartphone, label: "设备管理", page: "devices" as PageType },
    { icon: Settings, label: "运行配置", page: "config" as PageType },
    { icon: Shield, label: "账号检测", page: "account" as PageType },
  ];

  return (
    <>
      {/* 移动端遮罩 */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* 侧边栏 */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          bg-bg-surface border-r border-accent/6
          transform transition-all duration-300 ease-in-out
          ${isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
          ${isCollapsed ? "lg:w-20" : "lg:w-64"}
          w-64
        `}
      >
        <div className={`${isCollapsed ? "p-3" : "p-6"} h-full flex flex-col`}>
          {/* Logo 区域 */}
          <div className={`flex items-center ${isCollapsed ? "justify-center mb-4" : "justify-between mb-8"}`}>
            {!isCollapsed && <Logo />}
            {isCollapsed && (
              <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center shadow-lg shadow-accent/20">
                <span className="text-black font-bold text-lg">M</span>
              </div>
            )}
            <button
              onClick={onClose}
              className="lg:hidden text-muted-foreground hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 菜单 */}
          <nav className={`space-y-2 flex-1 ${isCollapsed ? "px-1" : ""}`}>
            {menuItems.map((item) => (
              <button
                key={item.label}
                title={isCollapsed ? item.label : undefined}
                onClick={() => {
                  onPageChange(item.page);
                  onClose();
                }}
                className={`
                  w-full flex items-center ${isCollapsed ? "justify-center px-2" : "gap-3 px-4"} py-3 rounded-xl
                  transition-all duration-200
                  ${
                    activePage === item.page
                      ? "bg-accent/10 text-accent border border-accent/20"
                      : "text-muted-foreground hover:text-white hover:bg-bg-hover"
                  }
                `}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {!isCollapsed && <span className="font-medium">{item.label}</span>}
              </button>
            ))}
          </nav>

          {/* 折叠按钮 */}
          <button
            onClick={onToggleCollapse}
            className="flex items-center justify-center w-full py-3 mb-4 rounded-xl text-muted-foreground hover:text-white hover:bg-bg-hover transition-all duration-200"
          >
            {isCollapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <ChevronLeft className="w-5 h-5" />
            )}
          </button>

          {/* 底部用户信息 */}
          <div className={`${isCollapsed ? "px-1" : ""}`}>
            <div className={`p-4 rounded-xl bg-bg-card border border-accent/6 ${isCollapsed ? "flex justify-center" : ""}`}>
              {isCollapsed ? (
                <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center">
                  <span className="text-accent font-semibold">U</span>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center">
                    <span className="text-accent font-semibold">U</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-white">用户</p>
                    <p className="text-xs text-muted-foreground">在线</p>
                  </div>
                  <button
                    className="text-muted-foreground hover:text-neon-red transition-colors"
                    onClick={async () => {
                      if (window.confirm("确定要关闭系统吗？所有设备将停止运行并归档数据。")) {
                        try {
                          await shutdown();
                          alert("系统正在关闭...");
                        } catch (e) {
                          alert("关闭失败: " + (e as Error).message);
                        }
                      }
                    }}
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

// 设备管理页面
function DevicesPage() {
  return (
    <>
      {/* 3D 机器人 + 日志区域 */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 运行日志 - 1/3 宽度 */}
        <div className="lg:col-span-1">
          <LogArea />
        </div>

        {/* 3D 机器人 - 2/3 宽度 */}
        <div className="lg:col-span-2">
          <SplineRobot />
        </div>
      </section>

      {/* ADB 设备连接 */}
      <section>
        <AdbPanel />
      </section>

      {/* 控制面板 */}
      <section>
        <Dashboard />
      </section>
    </>
  );
}

// 主页面
export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activePage, setActivePage] = useState<PageType>("devices");

  // 渲染当前页面
  const renderPage = () => {
    switch (activePage) {
      case "devices":
        return <DevicesPage />;
      case "config":
        return <ConfigPanel />;
      case "account":
        return <AccountCheckPanel />;
      default:
        return <DevicesPage />;
    }
  };

  // 获取页面标题
  const getPageTitle = () => {
    switch (activePage) {
      case "devices":
        return "设备管理";
      case "config":
        return "运行配置";
      case "account":
        return "账号检测";
      default:
        return "控制中心";
    }
  };

  return (
    <div className="flex h-screen bg-black overflow-hidden">
      {/* 侧边栏 */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        activePage={activePage}
        onPageChange={setActivePage}
      />

      {/* 主内容区 */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* 顶部导航栏 */}
        <header className="h-16 border-b border-accent/6 bg-bg-surface/50 backdrop-blur-sm flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden text-muted-foreground hover:text-white"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-semibold text-white">{getPageTitle()}</h1>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-4 py-2 rounded-lg bg-bg-card border border-accent/6">
              <div className="w-2 h-2 rounded-full bg-neon-green animate-pulse" />
              <span className="text-sm text-muted-foreground">系统正常</span>
            </div>
          </div>
        </header>

        {/* 可滚动内容区 */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-6 space-y-6">
            {renderPage()}
          </div>
        </div>
      </main>
    </div>
  );
}

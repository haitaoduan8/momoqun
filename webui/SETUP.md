# 🚀 快速启动指南

## 前置要求

- Node.js 18+ 
- npm 或 yarn 或 pnpm

## 安装步骤

### 1. 进入 webui 目录
```bash
cd webui
```

### 2. 安装依赖
```bash
npm install
# 或
yarn install
# 或
pnpm install
```

### 3. 启动开发服务器
```bash
npm run dev
# 或
yarn dev
# 或
pnpm dev
```

### 4. 访问应用
打开浏览器访问：**http://localhost:3000**

---

## ✨ 功能特性

### 🤖 Spline 3D 机器人
- 随鼠标转动的 3D 机器人
- 实时交互效果
- 流畅动画

### ✨ 鼠标光影效果
- Spotlight 聚光灯跟随鼠标
- 卡片发光边框
- 动态高亮效果

### 🎨 Neon Aurora 主题
- 极光青主色调 `#00FFC8`
- 纯黑背景 `#000000`
- 霓虹状态色
- 发光边框和阴影

### 📱 响应式设计
- 支持桌面端和移动端
- 侧边栏可折叠
- 自适应布局

---

## 🛠️ 技术栈

- **框架**：Next.js 14
- **UI 库**：React 18
- **样式**：Tailwind CSS
- **3D**：Spline (@splinetool/react-spline)
- **动画**：Framer Motion
- **图标**：Lucide React

---

## 📁 项目结构

```
webui/
├── app/
│   ├── layout.tsx          # 根布局
│   ├── page.tsx            # 主页面
│   └── globals.css         # 全局样式
├── components/
│   ├── ui/
│   │   ├── splite.tsx      # Spline 3D 组件
│   │   ├── spotlight.tsx   # 鼠标光影效果
│   │   └── card.tsx        # 卡片组件
│   ├── SplineRobot.tsx     # 3D 机器人展示
│   └── Dashboard.tsx       # 控制面板
├── lib/
│   └── utils.ts            # 工具函数
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

---

## 🎨 设计参考

### 颜色系统
```css
/* 主色调 */
--accent: #00FFC8;          /* 极光青 */
--accent-hover: #33FFD4;    /* 悬停态 */
--accent-dim: rgba(0,255,200,0.08);  /* 淡背景 */
--accent-glow: rgba(0,255,200,0.20); /* 发光 */

/* 背景色 */
--bg: #000000;              /* 纯黑 */
--bg-surface: #050508;      /* 面板 */
--bg-card: #0A0A0F;         /* 卡片 */

/* 状态色 */
--neon-green: #00FF88;      /* 成功 */
--neon-yellow: #FFB800;     /* 警告 */
--neon-red: #FF3355;        /* 错误 */
```

### 动画效果
```css
/* 聚光灯动画 */
@keyframes spotlight {
  0% { opacity: 0; transform: translate(-72%, -62%) scale(0.5); }
  100% { opacity: 1; transform: translate(-50%, -40%) scale(1); }
}

/* 发光动画 */
@keyframes glow {
  0% { box-shadow: 0 0 20px rgba(0,255,200,0.1); }
  100% { box-shadow: 0 0 40px rgba(0,255,200,0.2); }
}
```

---

## 🔧 自定义配置

### 修改主题色
编辑 `tailwind.config.ts`：
```typescript
colors: {
  accent: {
    DEFAULT: "#YOUR_COLOR",  // 修改主色
    // ...
  },
}
```

### 修改 3D 场景
编辑 `components/SplineRobot.tsx`：
```typescript
<SplineScene
  scene="YOUR_SPLINE_SCENE_URL"  // 替换为你的 Spline 场景
  className="w-full h-full"
/>
```

---

## 📚 相关资源

- [Spline 3D](https://spline.design) - 3D 设计工具
- [Next.js 文档](https://nextjs.org/docs) - 框架文档
- [Tailwind CSS](https://tailwindcss.com/docs) - 样式框架
- [Framer Motion](https://www.framer.com/motion/) - 动画库

---

## 🐛 常见问题

### Q: Spline 3D 加载慢？
A: Spline 场景文件较大，首次加载可能需要几秒。可以添加 loading 状态。

### Q: 鼠标光影不工作？
A: 确保父容器有 `position: relative` 和 `overflow: hidden`。

### Q: 样式不生效？
A: 检查 Tailwind CSS 配置，确保 content 路径正确。

---

**🎉 享受全新的 Neon Aurora 3D 控制中心体验！**

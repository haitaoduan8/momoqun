# 🌌 momoqun Web UI - Neon Aurora 3D 控制中心

## 🎯 你想要的效果

✅ **Spline 3D 机器人** - 随鼠标转动的 3D 机器人  
✅ **鼠标光影效果** - Spotlight 聚光灯跟随鼠标  
✅ **极光青主色调** - `#00FFC8` Neon Aurora 风格  
✅ **纯黑背景** - 深邃高级感  
✅ **发光边框** - 聚光灯效果  

---

## 🚀 快速启动

```bash
# 1. 进入 webui 目录
cd webui

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev

# 4. 访问应用
# 打开浏览器访问：http://localhost:3000
```

---

## ✨ 核心功能

### 🤖 Spline 3D 机器人
```tsx
<SplineScene
  scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
  className="w-full h-full"
/>
```
- 实时 3D 渲染
- 随鼠标转动
- 流畅动画效果

### ✨ 鼠标光影效果
```tsx
<Spotlight
  className="-top-40 left-0 md:left-60 md:-top-20"
  size={400}
/>
```
- 跟随鼠标移动
- 平滑弹簧动画
- 发光渐变效果

### 🎨 Neon Aurora 主题
```css
--accent: #00FFC8;          /* 极光青 */
--bg: #000000;              /* 纯黑 */
--neon-green: #00FF88;      /* 霓虹绿 */
--neon-yellow: #FFB800;     /* 琥珀金 */
--neon-red: #FF3355;        /* 霓虹红 */
```

---

## 📁 项目结构

```
webui/
├── app/
│   ├── layout.tsx          # 根布局（字体、元数据）
│   ├── page.tsx            # 主页面（3D 机器人 + 控制面板）
│   └── globals.css         # 全局样式（Neon Aurora 主题）
├── components/
│   ├── ui/
│   │   ├── splite.tsx      # Spline 3D 组件
│   │   ├── spotlight.tsx   # 鼠标光影效果
│   │   └── card.tsx        # 卡片组件
│   ├── SplineRobot.tsx     # 3D 机器人展示区
│   └── Dashboard.tsx       # 控制面板（设备管理）
├── lib/
│   └── utils.ts            # 工具函数（cn 合并）
├── package.json            # 依赖配置
├── tailwind.config.ts      # Tailwind 主题配置
└── tsconfig.json           # TypeScript 配置
```

---

## 🎨 设计亮点

### 1. 3D 机器人区域
```
┌─────────────────────────────────────────────┐
│  Interactive 3D                              │
│                                              │
│  随鼠标转动的 3D 机器人，配合聚光灯效果，     │
│  打造沉浸式控制中心体验。                     │
│                                              │
│  [开始使用]  [了解更多]                       │
│                              🤖 ← 3D 机器人  │
└─────────────────────────────────────────────┘
```

### 2. 鼠标光影效果
- 鼠标移动时，Spotlight 跟随
- 卡片边框发光
- 平滑动画过渡

### 3. 设备管理卡片
```
┌────────────────────────────────┐
│ 📱 设备 1        ● 运行中      │
│    127.0.0.1:5555              │
│    轮次: 42  好友: 156         │
│                                │
│  [▶ 开始]  [⏸ 暂停]  [🗑 删除] │
└────────────────────────────────┘
```

---

## 🛠️ 技术栈

| 技术 | 用途 |
|------|------|
| **Next.js 14** | React 框架 |
| **React 18** | UI 库 |
| **Tailwind CSS** | 样式框架 |
| **Spline** | 3D 渲染 |
| **Framer Motion** | 动画 |
| **Lucide React** | 图标 |

---

## 📚 关键代码

### Spline 3D 组件
```tsx
// components/ui/splite.tsx
'use client'
import { Suspense, lazy } from 'react'
const Spline = lazy(() => import('@splinetool/react-spline'))

export function SplineScene({ scene, className }: SplineSceneProps) {
  return (
    <Suspense fallback={<div className="loader"></div>}>
      <Spline scene={scene} className={className} />
    </Suspense>
  )
}
```

### Spotlight 鼠标光影
```tsx
// components/ui/spotlight.tsx
export function Spotlight({ className, size = 300 }: SpotlightProps) {
  const mouseX = useSpring(0, springOptions);
  const mouseY = useSpring(0, springOptions);
  
  // 鼠标移动时更新位置
  const handleMouseMove = useCallback((event: MouseEvent) => {
    mouseX.set(event.clientX - left);
    mouseY.set(event.clientY - top);
  }, []);

  return (
    <motion.div
      className="pointer-events-none absolute rounded-full blur-xl bg-gradient-to-b from-accent/30 via-accent/10 to-transparent"
      style={{ left: spotlightLeft, top: spotlightTop }}
    />
  );
}
```

---

## 🎯 下一步

1. **安装依赖**：`npm install`
2. **启动开发**：`npm run dev`
3. **访问应用**：http://localhost:3000
4. **移动鼠标**：体验 3D 机器人和光影效果！

---

## 📖 详细文档

- **SETUP.md** - 快速启动指南
- **README.md** - 项目说明

---

**🎉 享受全新的 Neon Aurora 3D 控制中心体验！**

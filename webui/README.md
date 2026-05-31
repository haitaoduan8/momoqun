# momoqun Web UI

基于 Next.js + React + Spline 3D 的现代化 Web UI，**已连接后端 API**。

## 特性

- 🤖 **Spline 3D 机器人** - 随鼠标转动的 3D 机器人
- ✨ **鼠标光影效果** - Spotlight 聚光灯跟随鼠标
- 🎨 **Neon Aurora 主题** - 极光青 + 纯黑背景
- 📱 **响应式设计** - 支持多设备
- 🔌 **实时数据** - 连接后端 API，实时显示设备状态

## 快速开始

### 1. 启动后端服务器

```bash
# 在项目根目录
python3 server.py --port 5100
```

### 2. 启动前端

```bash
# 进入 webui 目录
cd webui

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 3. 访问应用

- **前端**：http://localhost:3000
- **后端 API**：http://localhost:5100

## API 连接

前端已连接后端 FastAPI 服务器，支持以下功能：

| API 端点 | 功能 |
|---------|------|
| `GET /api/devices` | 获取设备列表 |
| `POST /api/devices/start` | 启动设备 |
| `POST /api/devices/pause` | 暂停设备 |
| `POST /api/devices/remove` | 删除设备 |
| `GET /api/stats` | 获取统计数据 |
| `GET /api/account-check/status` | 账号检测状态 |
| `POST /api/account-check/trigger` | 触发检测 |

## 配置

在 `.env.local` 中配置 API 地址：

```env
NEXT_PUBLIC_API_URL=http://localhost:5100
```

## 技术栈

- **框架**：Next.js 14
- **UI**：React + Tailwind CSS
- **3D**：Spline (@splinetool/react-spline)
- **动画**：Framer Motion
- **主题**：Neon Aurora (极光青 #00FFC8)

## 项目结构

```
webui/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── components/
│   ├── ui/
│   │   ├── splite.tsx          # Spline 3D 组件
│   │   ├── spotlight.tsx       # 鼠标光影效果
│   │   └── card.tsx            # 卡片组件
│   ├── SplineRobot.tsx         # 3D 机器人
│   ├── Dashboard.tsx           # 主控制面板 (已连接 API)
│   └── LogArea.tsx             # 日志区域
├── lib/
│   ├── api.ts                  # API 服务层
│   ├── hooks.ts                # React Hooks
│   └── utils.ts
├── .env.local                  # API 配置
├── package.json
└── tailwind.config.ts
```

## 设计参考

- **Spline 3D**：https://spline.design
- **Aceternity UI**：Spotlight 效果
- **Neon Aurora**：极光青主色调

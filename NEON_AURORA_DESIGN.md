# 🌌 Neon Aurora 设计系统

## 访问地址
**http://127.0.0.1:8550**

---

## 设计灵感

借鉴了以下现代 UI 设计风格：

### 1. Elegant Dark Pattern
- 深邃渐变背景
- 光线条纹效果
- 微妙点状纹理

### 2. Spotlight 聚光灯
- 聚光灯发光边框
- 动态光效
- 焦点高亮

### 3. Neumorphism 新拟态
- 柔和阴影层次
- 凸起/凹陷效果
- 触感反馈

### 4. Spline 3D 科技感
- 未来主义风格
- 流光效果
- 立体层次

---

## 核心特色

### 🎨 极光青主色调
```
主色：#00FFC8
悬停：#33FFD4
淡背景：rgba(0,255,200,0.08)
发光：rgba(0,255,200,0.20)
```

### 🌑 纯黑背景体系
```
纯黑：#000000
深空黑：#050508
星云黑：#0A0A0F
悬浮层：#0F0F15
```

### ✨ 霓虹状态色
```
成功：#00FF88（霓虹绿）
警告：#FFB800（琥珀金）
危险：#FF3355（霓虹红）
```

### 💡 聚光灯效果
- 卡片边框带青色微光
- 状态指示器发光
- 按钮发光阴影
- 输入框聚焦发光

---

## Logo 设计

```
┌─────────────┐
│  ┌───────┐  │
│  │   M   │  │  ← 青色渐变背景
│  └───────┘  │  ← 发光阴影
│   momoqun   │  ← 现代简约
└─────────────┘
```

- 青色渐变背景 `#00FFC8`
- 发光阴影效果
- 圆角设计（10px）
- 深色文字 `#000000`

---

## 组件升级

### 按钮系统
- **主按钮**：极光青实底 + 发光阴影
- **描边按钮**：青色微光边框
- **危险按钮**：霓虹红 + 发光
- **成功按钮**：霓虹绿 + 发光

### 卡片系统
- 圆角：20px
- 边框：青色微光 `rgba(0,255,200,0.06)`
- 阴影：柔和黑色 + 青色发光
- 背景：星云黑 `#0A0A0F`

### 输入框系统
- 圆角：12px
- 边框：青色微光
- 聚焦：明亮青色边框
- 光标：极光青

### 状态徽章
- 发光圆点
- 青色背景
- 精致边框

---

## 文件结构

```
ui/
├── theme.py           # 主题系统（Neon Aurora）
├── app.py             # 主窗口布局
├── adb_panel.py       # ADB 设备管理
├── config_panel.py    # 运行配置
├── device_list.py     # 设备卡片列表
├── account_check_panel.py  # 账号检测
└── log_area.py        # 日志输出区
```

---

## 使用示例

### 导入主题
```python
from ui.theme import (
    BG, BG_CARD, ACCENT, TEXT,
    card_container, accent_btn, section_title, badge,
    logo, logo_with_text, spotlight_container,
)
```

### 创建 Logo
```python
# 简单 Logo
logo_icon = logo(36)

# Logo + 文字
logo_with_text = logo_with_text(22)
```

### 创建聚光灯卡片
```python
card = spotlight_container(
    content=ft.Text("内容"),
    # 可选参数
    bgcolor=BG_CARD,
    border_radius=20,
)
```

### 创建发光按钮
```python
btn = accent_btn(
    text="点击",
    on_click=handler,
    icon=ft.Icons.PLAY,
    height=44,
)
```

---

## 设计原则

1. **极致黑色**：纯黑背景营造深邃氛围
2. **极光青光效**：所有强调元素使用青色
3. **聚光灯效果**：焦点元素带发光效果
4. **柔和阴影**：多层阴影营造层次感
5. **现代简约**：简洁的几何形状和间距

---

## 后续优化

1. 添加更多动画过渡效果
2. 考虑添加深色/浅色主题切换
3. 优化响应式布局
4. 添加更多微交互效果
5. 考虑集成 Spline 3D 效果

---

## 技术栈

- **框架**：Flet（Python Flutter）
- **设计语言**：Neon Aurora
- **主色调**：极光青 `#00FFC8`
- **背景**：纯黑 `#000000`
- **圆角**：12-20px
- **阴影**：多层柔和阴影

---

**🎉 享受全新的 Neon Aurora 设计体验！**

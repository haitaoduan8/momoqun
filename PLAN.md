# momoqun — 陌陌群聊邀请自动化

## 目标

1. 实时扫描「收到的招呼」
2. 有新招呼 → 逐个通过
3. 打开对话框，开始 N 轮聊天
4. N 轮后点「关注」
5. N+1 轮起检测互关好友
6. 非互关 → 发送自定义回关邀请 → 等待 → 重新检测（最多 M 次）
7. 互关 → 邀请进预设群聊 → 回到聊天列表继续扫描

## 架构

```
momoqun/
├── config/
│   ├── settings.yaml       # 所有可配参数
│   └── elements.yaml       # UI 元素映射 (从 Momo_Project 沿用)
├── core/
│   ├── driver.py           # [复用] DeviceHandler
│   ├── pipeline.py         # [新]   单好友流水线状态机
│   ├── greeter.py          # [改写] 招呼扫描 + 逐个通过
│   ├── chatter.py          # [新]   一对一多轮聊天
│   ├── group_invite.py     # [新]   群聊邀请
│   └── message_pool.py     # [复用] 消息池管理
├── actions/
│   ├── approve_greeting.py # [改写] 改为逐个通过模式
│   ├── mutual_friend.py    # [复用] 互关检测
│   ├── chat_topbar.py      # [复用] 顶栏通过/关注
│   └── ui_hierarchy.py     # [复用] UI 解析工具
├── data/
│   ├── storage.py          # [复用+扩展] friends.json
│   ├── friends.json        # 好友库
│   └── state.json          # 运行时状态
├── utils/
│   └── helpers.py          # 随机延迟、bounds 解析
├── main.py                 # 入口
└── .cursorrules            # 项目约定
```

## 核心状态机 (FriendPipeline)

```
WAIT_GREETING → ENTER_SAYHI → APPROVE → ENTER_CHAT
    → CHATTING (1..N) → CLICK_FOLLOW → CHECK_MUTUAL
    → [互关] INVITE_TO_GROUP → DONE
    → [非互关] SEND_INVITE_BACK → WAIT_PEER_REPLY → CHECK_MUTUAL_AGAIN
        → [M次后仍非互关] DONE
```

## 配置项

- greet_scan_interval_s: 招呼扫描间隔
- chat_rounds_before_follow: N (几轮后点关注)
- chat_strategy: "message_pool" | "ai" (待定，留接口)
- message_pools: 消息池列表
- invite_back_message: 自定义回关邀请文案
- max_mutual_checks: M (最多检测互关次数)
- group_name: 目标群聊名称
- reply_interval / click_offset / delay: 通用参数

## 复用的 Momo_Project 模块

| 模块 | 路径 | 修改 |
|------|------|------|
| DeviceHandler | core/driver.py | 无 |
| MessagePoolManager | core/message_pool.py | 无 |
| StorageHandler | data/storage.py | 扩展 status |
| detect_mutual | actions/mutual_friend_status.py | 无 |
| handle_chat_topbar | actions/chat_topbar_friend.py | 无 |
| GreetingManager | actions/approve_greeting.py | 改为逐个通过 |
| elements.yaml | config/elements.yaml | 无 |

## 聊天策略接口

```python
class ChatStrategy(ABC):
    """聊天策略抽象接口"""
    @abstractmethod
    def get_message(self, round_num: int, context: dict) -> str:
        """返回本轮要发送的消息"""
```

实现类：
- `MessagePoolStrategy` — 从消息池选
- `AIStrategy` — 调 AI 生成（后续实现）

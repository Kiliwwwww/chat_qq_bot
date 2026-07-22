# QQ Chat Bot

基于 NoneBot2 的 AI 聊天机器人，支持群聊概率回复、私聊白名单、图片识别等功能。

## 功能特性

- **AI 对话**：接入 OpenAI 兼容 API，支持上下文记忆
- **群聊概率回复**：可配置回复概率，避免刷屏
- **私聊白名单**：仅允许指定用户私聊
- **群聊白名单**：仅在指定群组启用
- **图片识别**：支持发送图片给 AI 分析
- **管理员系统**：通过命令管理白名单
- **冷却机制**：防止短时间内重复回复
- **排行榜功能**：基于 Redis 的每日群消息排行榜
- **微博动态**：查看微博用户最新动态和图片
- **欢迎语系统**：新成员入群自动发送欢迎语
- **复读检测**：自动跟随群友复读消息
- **表情贴纸**：自动给指定用户消息贴表情

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
```

主要配置项：

```env
# AI 配置
ai_api_key=你的API密钥
ai_base_url=https://api.example.com/v1
ai_model=模型名称

# 管理员QQ号
admin_qq=123456789

# 群消息回复概率 (0.0~1.0)
group_reply_chance=0.3
```

### 3. 运行机器人

```bash
python bot.py
```

### 4. 访问文档

启动后访问 http://localhost:8080/website/ 查看 API 文档。

## 命令说明

| 命令 | 别名 | 说明 |
|------|------|------|
| `/help` | `/帮助` | 显示帮助信息 |
| `/reset` | `/重置对话` | 重置当前对话历史 |
| `/settings <QQ号>` | `/设置` | 管理用户白名单（管理员） |
| `/groupsettings <群号>` | `/群设置` | 管理群白名单（管理员） |
| `/setkey <关键词> <含义>` | `/设置关键词` | 设置关键词映射（管理员） |
| `/邻家大姐姐人格` | - | 切换到邻家大姐姐人格 |
| `/雌小鬼人格` | - | 切换回默认人格 |
| `/贴表情 <QQ号>` | - | 给指定用户消息贴随机表情（管理员） |
| `/取消贴表情 <QQ号>` | - | 取消给指定用户贴的表情（管理员） |
| `/全体贴表情` | - | 给群内所有人消息随机贴表情（管理员） |
| `/取消全体贴表情` | - | 取消全体贴表情（管理员） |
| `/贴表情all <QQ号>` | - | 给指定用户在所有群贴表情（管理员） |
| `/取消贴表情all <QQ号>` | - | 取消指定用户在所有群的贴表情（管理员） |
| `/闭嘴` | - | 让机器人静默5分钟（管理员） |
| `/欢迎语 <内容>` | - | 设置群欢迎语（管理员） |
| `/排行榜` | `/ranking` | 查看今日群消息排行榜 |
| `/weibo <UID>` | - | 查看微博用户最新动态（私聊） |
| `/sendweibo <UID> <群号>` | - | 发送微博图片到指定群（私聊） |

## 配置说明

在 `.env` 文件中配置以下参数：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ai_api_key` | - | OpenAI API 密钥 |
| `ai_base_url` | `https://api.xiaomimimo.com/v1` | API 地址 |
| `ai_model` | `mimo-v2.5` | 模型名称 |
| `ai_max_tokens` | `1024` | 最大生成长度 |
| `ai_temperature` | `1.0` | 生成温度 |
| `ai_top_p` | `0.95` | Top P 采样 |
| `admin_qq` | - | 管理员 QQ 号 |
| `admin_name` | `宝宝葵` | 管理员昵称（用于提示词替换） |
| `group_reply_chance` | `0.3` | 群聊回复概率 (0.0~1.0) |
| `random_repeat_chance` | `0.03` | 随机复读群友消息概率 (0.0~1.0) |
| `group_emoji_chance` | `0.3` | 全体贴表情概率 (0.0~1.0) |
| `global_emoji_id` | `46` | 全局贴表情的emoji_id |
| `ai_debug_log` | `false` | 是否启用 AI 调试日志 |
| `NICKNAME` | `[]` | 机器人昵称（建议留空） |

### Redis 配置（排行榜功能依赖）

在 `config.py` 中配置 Redis 连接参数：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `redis_host` | `localhost` | Redis 服务器地址 |
| `redis_port` | `6379` | Redis 端口 |
| `redis_db` | `0` | Redis 数据库编号 |
| `redis_password` | `""` | Redis 密码 |
| `redis_decode_responses` | `True` | 自动解码响应 |

## 项目结构

```
qqbot/
├── bot.py                  # 入口文件
├── config.py               # 全局配置（Redis等）
├── .env                    # 配置文件
├── pyproject.toml          # 项目配置
├── requirements.txt        # 依赖列表
├── data/
│   └── md/
│       ├── system_prompt.md      # AI 默认系统提示词
│       └── system_prompt_kind.md # 邻家大姐姐人格提示词
└── plugins/
    ├── chat_ai/            # AI 聊天插件
    │   ├── __init__.py     # 插件初始化
    │   ├── config.py       # 配置模型
    │   ├── database.py     # 数据库操作
    │   ├── service.py      # AI 服务封装
    │   ├── state.py        # 全局状态管理
    │   ├── commands/       # 命令处理器
    │   │   ├── __init__.py
    │   │   ├── help.py     # 帮助命令
    │   │   ├── personality.py  # 人格切换命令
    │   │   └── admin.py    # 管理员命令
    │   ├── handlers/       # 消息处理器
    │   │   ├── __init__.py
    │   │   ├── private.py  # 私聊消息处理
    │   │   └── group.py    # 群消息处理
    │   └── utils/          # 工具函数
    │       ├── __init__.py
    │       └── helpers.py  # 辅助函数
    ├── ranking/            # 排行榜插件（基于Redis）
    │   ├── __init__.py     # 插件初始化
    │   └── config.py       # Redis配置
    └── weibo/              # 微博动态插件
        ├── __init__.py     # 插件初始化
        └── config.py       # 插件配置
```

## 注意事项

- `.env` 文件包含敏感信息，已被 `.gitignore` 忽略
- `NICKNAME` 配置建议设置为空列表 `[]`，避免概率回复失效
- 首次使用需要通过管理员命令添加群/用户白名单
- 人格切换功能支持"雌小鬼"（默认）和"邻家大姐姐"两种人格
- 表情功能需要机器人具有设置消息表情的权限
- 排行榜功能需要 Redis 服务支持，数据保留 2 天
- 微博功能仅支持私聊使用，需要用户在白名单中
- 欢迎语功能需要机器人具有群成员加入通知权限
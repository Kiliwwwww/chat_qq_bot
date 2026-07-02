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
| `group_reply_chance` | `0.3` | 群聊回复概率 (0.0~1.0) |
| `NICKNAME` | `[]` | 机器人昵称（建议留空） |

## 项目结构

```
chat_qq_bot/
├── bot.py                  # 入口文件
├── .env                    # 配置文件
├── pyproject.toml          # 项目配置
├── requirements.txt        # 依赖列表
├── data/
│   └── md/
│       └── system_prompt.md  # AI 系统提示词
└── plugins/
    ├── echo.py             # 复读机插件
    └── chat_ai/
        ├── __init__.py     # 主要逻辑
        ├── config.py       # 配置模型
        ├── database.py     # 数据库操作
        └── service.py      # AI 服务封装
```

## 注意事项

- `.env` 文件包含敏感信息，已被 `.gitignore` 忽略
- `NICKNAME` 配置建议设置为空列表 `[]`，避免概率回复失效
- 首次使用需要通过管理员命令添加群/用户白名单
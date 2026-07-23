# Docker 部署文档

## 前置要求

- Docker >= 20.10
- Docker Compose >= 2.0

## 快速开始

### 1. 配置环境变量

复制环境变量模板并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下必要参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| `ai_api_key` | AI API 密钥 | `sk-xxx` |
| `ai_base_url` | AI API 地址 | `https://api.example.com/v1` |
| `ai_model` | AI 模型名称 | `mimo-v2.5` |
| `admin_qq` | 管理员 QQ 号 | `123456789` |
| `SUPERUSERS` | NoneBot 超级用户 | `["123456789"]` |

Redis 配置（Docker 环境会自动覆盖）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `redis_host` | `redis` | Redis 地址（Docker 内自动设为 redis 服务） |
| `redis_port` | `6379` | Redis 端口 |
| `redis_db` | `0` | Redis 数据库 |
| `redis_password` | 空 | Redis 密码 |

### 2. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f qqbot

# 查看所有服务状态
docker-compose ps
```

### 3. 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷（会清除 Redis 数据）
docker-compose down -v
```

## 服务说明

### qqbot 服务

- **端口**: 8080
- **数据卷**:
  - `./data` → `/app/data`：持久化数据（SQLite 数据库、AI 提示词等）
  - `./log` → `/app/log`：日志文件
  - `./.env` → `/app/.env`：环境变量配置（只读）

### redis 服务

- **端口**: 6379
- **数据卷**: `redis-data`：Redis 持久化数据
- **特性**: 开启 AOF 持久化，数据不会丢失

## 常用命令

```bash
# 重新构建镜像（代码更新后）
docker-compose build
docker-compose up -d

# 进入容器调试
docker-compose exec qqbot bash

# 查看 Redis 数据
docker-compose exec redis redis-cli

# 重启单个服务
docker-compose restart qqbot
```

## 配置 OneBot 适配器

在你的 QQ 机器人框架（如 go-cqhttp）中，配置 WebSocket 反向连接地址：

```
ws://localhost:8080/onebot/v11/ws
```

如果机器人框架也运行在 Docker 中，使用：

```
ws://qqbot:8080/onebot/v11/ws
```

## 数据备份

### Redis 数据

```bash
# 备份 Redis 数据
docker-compose exec redis redis-cli BGSAVE
docker cp qqbot-redis:/data/dump.rdb ./backup/dump.rdb
```

### 应用数据

```bash
# 备份 data 目录
cp -r ./data ./backup/data_$(date +%Y%m%d)
```

## 故障排查

### 查看日志

```bash
# 查看应用日志
docker-compose logs -f qqbot

# 查看 Redis 日志
docker-compose logs -f redis
```

### Redis 连接失败

1. 检查 Redis 服务是否正常运行：`docker-compose ps`
2. 检查 Redis 日志：`docker-compose logs redis`
3. 测试 Redis 连接：`docker-compose exec redis redis-cli ping`

### 端口冲突

如果 8080 或 6379 端口被占用，修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "18080:8080"  # 将宿主机端口改为 18080
```

## 生产环境建议

1. **修改 Redis 密码**：在 `.env` 中设置 `redis_password`，并在 `docker-compose.yml` 中添加 Redis 命令参数
2. **限制资源**：在 `docker-compose.yml` 中添加资源限制
3. **日志管理**：配置日志驱动和轮转
4. **监控**：配置健康检查和监控告警

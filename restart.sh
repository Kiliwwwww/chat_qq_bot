#!/bin/bash

# 切换到脚本所在目录
cd /Users/kiki/Code/python/qqbot

# 创建log目录
mkdir -p log

# 杀死之前的进程（通过PID文件）
if [ -f log/bot.pid ]; then
    PID=$(cat log/bot.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "杀死进程 $PID"
        kill -9 "$PID" 2>/dev/null
        sleep 1
    fi
    rm -f log/bot.pid
fi

# 备份旧日志
if [ -f log/run.log ]; then
    mv log/run.log "log/run_$(date +%Y%m%d_%H%M%S).log"
fi

# 备份AI日志
if [ -f log/ai_log.log ]; then
    mv log/ai_log.log "log/ai_log_$(date +%Y%m%d_%H%M%S).log"
fi

# 启动服务（后台运行，日志输出到log/run.log）
nohup python3 bot.py > log/run.log 2>&1 &
PID=$!
echo $PID > log/bot.pid
echo "服务已启动，PID: $PID，日志文件: log/run.log"

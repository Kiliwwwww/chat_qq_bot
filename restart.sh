#!/bin/bash

# 杀死占用8080端口的服务
lsof -ti:8081 | xargs kill -9 2>/dev/null
sleep 1

# 启动服务
cd /Users/kiki/Code/python/qqbot
python3 bot.py
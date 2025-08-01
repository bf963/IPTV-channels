#!/bin/bash

# 启动cron服务
service cron start

# 检查cron是否成功启动
if pgrep cron > /dev/null; then
    echo "Cron服务已成功启动"
else
    echo "Cron服务启动失败，尝试直接启动cron守护进程"
    /usr/sbin/cron
    sleep 1
    if pgrep cron > /dev/null; then
        echo "Cron守护进程已成功启动"
    else
        echo "警告：无法启动Cron服务"
    fi
fi

# 启动Flask应用
flask run --host 0.0.0.0

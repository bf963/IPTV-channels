#!/bin/bash

# 启动cron服务
service cron start
# IPTV 平台网段经 .9 转发 (重启自动恢复)
ip route add 182.138.0.0/16 via 192.168.5.9 2>/dev/null || true
ip route add 182.139.0.0/16 via 192.168.5.9 2>/dev/null || true
ip route add 220.167.0.0/16 via 192.168.5.9 2>/dev/null || true

# 启动Flask应用
flask run --host 0.0.0.0

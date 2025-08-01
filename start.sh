#!/bin/bash

# 启动cron服务
service cron start



# 启动Flask应用
flask run --host 0.0.0.0

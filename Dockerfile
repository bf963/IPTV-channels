#基于的基础镜像
FROM python:3.11.6-slim-bullseye

#代码添加到app文件夹
ADD . /app
# 设置app文件夹是工作目录
WORKDIR /app

ENV PYTHONUNBUFFERED=0
# 安装支持
EXPOSE 5000
ENV FLASK_APP=app.py
ENV TIME_ZONE Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends cron && rm -rf /var/lib/apt/lists/* && apt-get clean 

RUN pip install --no-cache-dir -r requirements.txt

#/usr/local/lib/python3.11/site-packages/Crypto/Cipher/DES3.py 84、85
RUN sed -i '84 s/^/#/' /usr/local/lib/python3.11/site-packages/Crypto/Cipher/DES3.py
RUN sed -i '85 s/^/#/' /usr/local/lib/python3.11/site-packages/Crypto/Cipher/DES3.py

RUN ln -snf /usr/share/zoneinfo/$TIME_ZONE /etc/localtime && echo $TIME_ZONE > /etc/timezone

ENV LC_ALL C.UTF-8

# 添加启动脚本并设置执行权限
# COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# 使用启动脚本作为容器的入口点
CMD ["/bin/bash", "/app/start.sh"]
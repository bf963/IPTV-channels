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

RUN apt-get update && apt-get install -y --no-install-recommends cron && rm -rf /var/lib/apt/lists/* && apt-get clean 

RUN pip install --no-cache-dir -r requirements.txt
#CMD ["python", "/app/app.py"]

#/usr/local/lib/python3.11/site-packages/Crypto/Cipher/DES3.py 84、85
RUN sed -i '84 s/^/#/' /usr/local/lib/python3.11/site-packages/Crypto/Cipher/DES3.py
RUN sed -i '85 s/^/#/' /usr/local/lib/python3.11/site-packages/Crypto/Cipher/DES3.py

ENV LC_ALL C.UTF-8
ENTRYPOINT [ "flask"]
CMD [ "run", "--host", "0.0.0.0" ]
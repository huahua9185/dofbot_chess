# Web网关服务 - 生产环境Dockerfile
FROM python:3.9-slim

LABEL maintainer="chess_robot_team"
LABEL version="1.0.0"
LABEL description="Chess Robot Web Gateway Service"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements文件
COPY shared/requirements.txt /tmp/shared_requirements.txt
COPY services/web_gateway/requirements.txt /tmp/gateway_requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/shared_requirements.txt && \
    pip install --no-cache-dir -r /tmp/gateway_requirements.txt

# 复制共享模块
COPY shared /app/shared

# 复制服务代码
COPY services/web_gateway/src /app

# 创建非root用户
RUN groupadd -r chess_robot && useradd -r -g chess_robot chess_robot
RUN chown -R chess_robot:chess_robot /app
USER chess_robot

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
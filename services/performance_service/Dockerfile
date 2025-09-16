# 性能监控服务Docker镜像
FROM python:3.9-slim

LABEL maintainer="Chess Robot Team"
LABEL description="Chess Robot Performance Service"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    htop \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY ../../requirements.txt /app/requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装额外的性能监控依赖
RUN pip install --no-cache-dir \
    psutil==5.9.5 \
    pynvml==11.5.0

# 复制服务代码
COPY . /app/
COPY ../../shared /app/shared/

# 创建必要目录
RUN mkdir -p /app/logs /app/data

# 设置环境变量
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# 暴露端口
EXPOSE 8008

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

# 启动服务
CMD ["python", "main.py"]
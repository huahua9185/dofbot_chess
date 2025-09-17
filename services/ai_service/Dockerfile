# AI引擎服务 - 生产环境Dockerfile
FROM python:3.9-slim

LABEL maintainer="chess_robot_team"
LABEL version="1.0.0"
LABEL description="Chess Robot AI Engine Service"

# 设置工作目录
WORKDIR /app

# 安装系统依赖和构建工具
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# 从源码编译安装Stockfish（适用于ARM架构）
RUN cd /tmp && \
    git clone --depth 1 --branch sf_16.1 https://github.com/official-stockfish/Stockfish.git && \
    cd Stockfish/src && \
    make -j$(nproc) build ARCH=armv8 && \
    cp stockfish /usr/local/bin/ && \
    cd / && \
    rm -rf /tmp/Stockfish

# 复制requirements文件
COPY shared/requirements.txt /tmp/shared_requirements.txt
COPY services/ai_service/requirements.txt /tmp/ai_service_requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/shared_requirements.txt && \
    pip install --no-cache-dir -r /tmp/ai_service_requirements.txt

# 复制共享模块
COPY shared /app/shared

# 复制服务代码
COPY services/ai_service/src /app

# 创建非root用户
RUN groupadd -r chess_robot && useradd -r -g chess_robot chess_robot
RUN chown -R chess_robot:chess_robot /app
USER chess_robot

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD stockfish bench 16 1 1 1 > /dev/null || exit 1

# 启动命令
CMD ["python", "-m", "ai.service"]
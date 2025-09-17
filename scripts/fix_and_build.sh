#!/bin/bash

# 修复依赖包冲突并重新构建镜像

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🔧 修复依赖包冲突并重新构建镜像"
echo "================================"

# 停止现有服务
log_info "停止现有服务..."
docker-compose -f docker-compose.simple.yml down 2>/dev/null || true

# 清理现有镜像
log_info "清理现有镜像..."
docker rmi chess-robot/web-gateway:latest 2>/dev/null || true
docker rmi chess-robot/game-manager:latest 2>/dev/null || true
docker rmi chess-robot/ai-engine:latest 2>/dev/null || true

# 构建Web网关服务（使用稳定依赖）
log_info "构建Web网关服务..."
cat > /tmp/web_gateway_fixed.dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制稳定的依赖文件
COPY shared/requirements.stable.txt /tmp/shared_requirements.txt
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

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

docker build -t chess-robot/web-gateway:latest -f /tmp/web_gateway_fixed.dockerfile .

# 构建游戏管理服务
log_info "构建游戏管理服务..."
cat > /tmp/game_manager_fixed.dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制稳定的依赖文件
COPY shared/requirements.stable.txt /tmp/shared_requirements.txt
COPY services/game_manager/requirements.txt /tmp/game_manager_requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/shared_requirements.txt && \
    pip install --no-cache-dir -r /tmp/game_manager_requirements.txt

# 复制共享模块
COPY shared /app/shared

# 复制服务代码
COPY services/game_manager/src /app

# 创建非root用户
RUN groupadd -r chess_robot && useradd -r -g chess_robot chess_robot
RUN chown -R chess_robot:chess_robot /app
USER chess_robot

# 启动命令
CMD ["python", "/app/main.py"]
EOF

docker build -t chess-robot/game-manager:latest -f /tmp/game_manager_fixed.dockerfile .

# 构建AI引擎服务
log_info "构建AI引擎服务..."
cat > /tmp/ai_engine_fixed.dockerfile << 'EOF'
FROM python:3.9-slim

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

# 复制稳定的依赖文件
COPY shared/requirements.stable.txt /tmp/shared_requirements.txt
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
EOF

docker build -t chess-robot/ai-engine:latest -f /tmp/ai_engine_fixed.dockerfile .

# 清理临时文件
rm -f /tmp/*_fixed.dockerfile

log_info "✅ 所有镜像构建完成"

# 显示构建的镜像
echo ""
log_info "构建的镜像列表:"
docker images | grep chess-robot

echo ""
log_info "🎉 依赖包冲突已修复，可以重新启动服务"
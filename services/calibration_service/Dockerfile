# 标定服务 - 生产环境Dockerfile
FROM python:3.9-slim

LABEL maintainer="chess_robot_team"
LABEL version="1.0.0"
LABEL description="Chess Robot Calibration Service"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    python3-opencv \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgtk-3-0 \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements文件
COPY shared/requirements.txt /tmp/shared_requirements.txt
COPY services/calibration_service/requirements.txt /tmp/calibration_requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/shared_requirements.txt && \
    pip install --no-cache-dir -r /tmp/calibration_requirements.txt

# 复制共享模块
COPY shared /app/shared

# 复制服务代码
COPY services/calibration_service /app

# 创建非root用户 (但需要访问硬件设备)
RUN groupadd -r chess_robot && useradd -r -g chess_robot chess_robot
RUN usermod -a -G video,dialout chess_robot
RUN chown -R chess_robot:chess_robot /app

# 创建数据目录
RUN mkdir -p /app/data/calibration && \
    chown -R chess_robot:chess_robot /app/data

USER chess_robot

# 暴露端口
EXPOSE 8002

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/status || exit 1

# 启动命令
CMD ["python", "calibration_service.py"]
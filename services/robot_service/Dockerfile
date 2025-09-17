# 机器人控制服务 - 生产环境Dockerfile
FROM python:3.9-slim

LABEL maintainer="chess_robot_team"
LABEL version="1.0.0"
LABEL description="Chess Robot Controller Service"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements文件
COPY shared/requirements.txt /tmp/shared_requirements.txt
COPY services/robot_service/requirements.txt /tmp/robot_service_requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/shared_requirements.txt && \
    pip install --no-cache-dir -r /tmp/robot_service_requirements.txt

# 复制共享模块
COPY shared /app/shared

# 复制服务代码
COPY services/robot_service/src /app

# 创建非root用户 (但需要访问串口设备)
RUN groupadd -r chess_robot && useradd -r -g chess_robot chess_robot
RUN usermod -a -G dialout chess_robot
RUN chown -R chess_robot:chess_robot /app
USER chess_robot

# 启动命令
CMD ["python", "-m", "robot.service"]
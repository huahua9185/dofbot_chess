#!/bin/bash
# Jetson Orin Nano开发环境安装脚本

set -e

echo "=== Jetson Orin Nano开发环境配置 ==="

# 检查是否运行在Jetson设备上
if ! grep -q "tegra" /proc/version; then
    echo "警告: 当前系统可能不是Jetson设备"
fi

# 1. 系统更新
echo "更新系统软件包..."
sudo apt update && sudo apt upgrade -y

# 2. 安装基础开发工具
echo "安装基础开发工具..."
sudo apt install -y \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    vim \
    htop \
    tree \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

# 3. 安装Python开发环境
echo "安装Python开发环境..."
sudo apt install -y \
    python3.9 \
    python3.9-dev \
    python3-pip \
    python3-venv \
    python3-setuptools \
    python3-wheel

# 创建Python虚拟环境
echo "创建Python虚拟环境..."
python3 -m venv /home/jetson/prog/venv
source /home/jetson/prog/venv/bin/activate

# 升级pip
pip install --upgrade pip setuptools wheel

# 4. 安装深度学习依赖 (Jetson专用)
echo "安装深度学习依赖..."

# 安装PyTorch for Jetson
if [ ! -f "/tmp/torch-2.0.0-cp39-cp39-linux_aarch64.whl" ]; then
    echo "下载PyTorch for Jetson..."
    wget https://nvidia.box.com/shared/static/p57jwntv436lfrd78inwl7iml6p13fzh.whl \
         -O /tmp/torch-2.0.0-cp39-cp39-linux_aarch64.whl
fi

pip install /tmp/torch-2.0.0-cp39-cp39-linux_aarch64.whl

# 安装torchvision
pip install torchvision==0.15.0

# 5. 安装OpenCV和视觉处理库
echo "安装OpenCV和视觉处理库..."
pip install \
    opencv-python==4.8.0.74 \
    numpy==1.24.3 \
    pillow==10.0.0 \
    matplotlib==3.7.2 \
    scikit-image==0.21.0

# 6. 安装机器人控制库
echo "安装机器人控制库..."
pip install \
    pyserial==3.5 \
    scipy==1.10.1 \
    pandas==2.0.3

# 7. 安装象棋AI库
echo "安装象棋AI库..."
pip install \
    stockfish==3.28.0 \
    python-chess==1.999

# 8. 安装Web框架和API库
echo "安装Web框架..."
pip install \
    fastapi==0.104.0 \
    uvicorn==0.23.2 \
    websockets==11.0.3 \
    pydantic==2.4.2 \
    python-multipart==0.0.6 \
    python-jose==3.3.0 \
    passlib==1.7.4 \
    bcrypt==4.0.1

# 9. 安装数据库驱动
echo "安装数据库驱动..."
pip install \
    motor==3.3.1 \
    aioredis==5.0.0 \
    pymongo==4.5.0

# 10. 安装测试框架
echo "安装测试框架..."
pip install \
    pytest==7.4.2 \
    pytest-asyncio==0.21.1 \
    pytest-mock==3.11.1

# 11. 安装监控和日志库
echo "安装监控和日志库..."
pip install \
    prometheus-client==0.17.1 \
    structlog==23.1.0 \
    psutil==5.9.5

# 12. Docker安装
echo "安装Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# 13. Docker Compose安装
echo "安装Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" \
         -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# 14. 设置用户权限
echo "设置用户权限..."
sudo usermod -aG docker $USER
sudo usermod -aG dialout $USER  # 串口权限
sudo usermod -aG video $USER    # 摄像头权限

# 15. 创建必要的目录
echo "创建项目目录..."
mkdir -p /home/jetson/prog/{logs,models,calibration,data/images,scripts}

# 16. 生成requirements.txt
echo "生成requirements.txt..."
cat > /home/jetson/prog/requirements.txt << EOF
# 深度学习和视觉处理
torch==2.0.0
torchvision==0.15.0
opencv-python==4.8.0.74
numpy==1.24.3
pillow==10.0.0
matplotlib==3.7.2
scikit-image==0.21.0

# 机器人控制
pyserial==3.5
scipy==1.10.1
pandas==2.0.3

# 象棋AI
stockfish==3.28.0
python-chess==1.999

# Web框架
fastapi==0.104.0
uvicorn==0.23.2
websockets==11.0.3
pydantic==2.4.2
python-multipart==0.0.6
python-jose==3.3.0
passlib==1.7.4
bcrypt==4.0.1

# 数据库
motor==3.3.1
aioredis==5.0.0
pymongo==4.5.0

# 测试
pytest==7.4.2
pytest-asyncio==0.21.1
pytest-mock==3.11.1

# 监控和日志
prometheus-client==0.17.1
structlog==23.1.0
psutil==5.9.5
EOF

# 17. 创建环境变量配置
echo "创建环境变量配置..."
cat > /home/jetson/prog/.env.example << EOF
# 数据库配置
MONGO_PASSWORD=your_mongo_password_here
REDIS_URL=redis://localhost:6379

# 安全配置
JWT_SECRET=your_jwt_secret_here
ENCRYPTION_KEY=your_encryption_key_here

# 硬件配置
ROBOT_PORT=/dev/ttyUSB0
ROBOT_BAUDRATE=115200
CAMERA_RGB_ID=0
CAMERA_DEPTH_ID=1

# AI配置
STOCKFISH_PATH=/usr/games/stockfish
AI_DEFAULT_DIFFICULTY=3
AI_MAX_THINKING_TIME=10

# Web配置
WEB_HOST=0.0.0.0
WEB_PORT=8080
CORS_ORIGINS=["http://localhost:3000"]

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=/home/jetson/prog/logs

# 监控配置
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30
EOF

echo "=== 开发环境配置完成 ==="
echo ""
echo "注意事项:"
echo "1. 请重新登录以使权限生效"
echo "2. 复制 .env.example 到 .env 并填写实际配置"
echo "3. 激活虚拟环境: source /home/jetson/prog/venv/bin/activate"
echo "4. 确保硬件设备正确连接"
echo ""
echo "验证安装:"
echo "- Python版本: $(python3 --version)"
echo "- Docker版本: $(docker --version 2>/dev/null || echo 'Docker未安装')"
echo "- 可用内存: $(free -h | grep '^Mem:' | awk '{print $7}')"
#!/bin/bash
# 创建Python虚拟环境的轻量级脚本

set -e

PROJECT_ROOT="/home/jetson/prog"
cd $PROJECT_ROOT

echo "=== 创建Python虚拟环境 ==="

# 检查是否已存在虚拟环境
if [ -d "venv" ]; then
    echo "虚拟环境已存在，跳过创建"
else
    echo "创建Python虚拟环境..."
    python3 -m venv venv
    echo "虚拟环境创建完成"
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "升级pip..."
pip install --upgrade pip setuptools wheel

# 安装基础依赖（仅安装不需要编译的包）
echo "安装基础依赖包..."
pip install \
    fastapi==0.104.0 \
    uvicorn==0.23.2 \
    pydantic==2.4.2 \
    python-multipart==0.0.6 \
    python-jose==3.3.0 \
    passlib==1.7.4 \
    bcrypt==4.0.1 \
    pytest==7.4.2 \
    pytest-asyncio==0.21.1 \
    pytest-mock==3.11.1 \
    prometheus-client==0.17.1 \
    psutil==5.9.5

echo "基础Python环境设置完成！"
echo ""
echo "注意："
echo "1. 激活虚拟环境: source venv/bin/activate"
echo "2. 要安装完整依赖，请运行: pip install -r requirements.txt"
echo "3. 某些包（如PyTorch、OpenCV）需要特殊安装步骤，请参考setup_jetson_env.sh"
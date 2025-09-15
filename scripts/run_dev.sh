#!/bin/bash
# 开发环境启动脚本

set -e

PROJECT_ROOT="/home/jetson/prog"
cd $PROJECT_ROOT

echo "=== 启动智能象棋机器人开发环境 ==="

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在，请先运行 setup_jetson_env.sh"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate
echo "已激活Python虚拟环境"

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "警告: .env文件不存在，使用默认配置"
    cp .env.example .env
fi

# 设置Python路径
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

# 创建日志目录
mkdir -p logs models calibration data/images

echo "开发环境准备就绪！"
echo ""
echo "可用的开发命令:"
echo "  - pytest tests/                    # 运行测试"
echo "  - python -m services.vision_service.src.main  # 启动视觉服务"
echo "  - python -m services.robot_control_service.src.main  # 启动机器人控制服务"
echo "  - python -m services.ai_engine_service.src.main      # 启动AI引擎服务"
echo ""
echo "项目结构:"
tree -L 2 -I '__pycache__|*.pyc|venv'
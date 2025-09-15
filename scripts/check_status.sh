#!/bin/bash
# 项目状态检查脚本

set -e

PROJECT_ROOT="/home/jetson/prog"
cd $PROJECT_ROOT

echo "=== 智能象棋机器人项目状态检查 ==="
echo ""

# 检查系统信息
echo "📋 系统信息:"
echo "  - 操作系统: $(uname -sro)"
echo "  - 可用内存: $(free -h | grep '^Mem:' | awk '{print $7}')"
echo "  - 磁盘空间: $(df -h / | awk 'NR==2 {print $4}')"
echo ""

# 检查Python环境
echo "🐍 Python环境:"
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "  - Python版本: $(python --version)"
    echo "  - Pip版本: $(pip --version | cut -d' ' -f1-2)"
    echo "  - 虚拟环境: ✅ 已创建"
else
    echo "  - 虚拟环境: ❌ 未创建"
fi
echo ""

# 检查必要文件
echo "📁 项目文件:"
files=(
    "requirements.txt"
    ".env.example"
    "CLAUDE.md"
    "README.md"
    "shared/utils/logger.py"
    "shared/utils/redis_client.py"
    "shared/models/chess_models.py"
    "shared/config/settings.py"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file: ✅"
    else
        echo "  - $file: ❌"
    fi
done
echo ""

# 检查目录结构
echo "🏗️  目录结构:"
directories=(
    "services/vision_service"
    "services/robot_control_service"
    "services/ai_engine_service"
    "services/game_manager_service"
    "services/web_gateway_service"
    "infrastructure/docker"
    "shared/utils"
    "tests/unit"
    "web_ui/src"
)

for dir in "${directories[@]}"; do
    if [ -d "$dir" ]; then
        echo "  - $dir: ✅"
    else
        echo "  - $dir: ❌"
    fi
done
echo ""

# 检查硬件设备 (如果在Jetson上运行)
echo "🔌 硬件设备检查:"
if [ -c "/dev/video0" ]; then
    echo "  - RGB相机 (/dev/video0): ✅"
else
    echo "  - RGB相机 (/dev/video0): ❌"
fi

if [ -c "/dev/video1" ]; then
    echo "  - 深度相机 (/dev/video1): ✅"
else
    echo "  - 深度相机 (/dev/video1): ❌ (可能正常，取决于相机型号)"
fi

if [ -c "/dev/ttyUSB0" ]; then
    echo "  - 机器人串口 (/dev/ttyUSB0): ✅"
else
    echo "  - 机器人串口 (/dev/ttyUSB0): ❌ (需要连接DofBot Pro)"
fi
echo ""

# 检查Docker (如果已安装)
echo "🐳 Docker状态:"
if command -v docker &> /dev/null; then
    echo "  - Docker: ✅ $(docker --version)"
    if command -v docker-compose &> /dev/null; then
        echo "  - Docker Compose: ✅ $(docker-compose --version)"
    else
        echo "  - Docker Compose: ❌"
    fi
else
    echo "  - Docker: ❌ 未安装"
fi
echo ""

# 统计代码行数
echo "📊 代码统计:"
if command -v find &> /dev/null; then
    python_lines=$(find . -name "*.py" -not -path "./venv/*" | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
    echo "  - Python代码行数: $python_lines"

    file_count=$(find . -name "*.py" -not -path "./venv/*" | wc -l)
    echo "  - Python文件数量: $file_count"
fi
echo ""

echo "✅ 状态检查完成！"
echo ""
echo "下一步操作建议:"
echo "1. 如果虚拟环境未创建，运行: ./scripts/setup_jetson_env.sh"
echo "2. 启动开发环境: ./scripts/run_dev.sh"
echo "3. 连接硬件设备并测试"
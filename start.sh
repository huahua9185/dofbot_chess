#!/bin/bash

# 象棋机器人系统快速启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🤖 启动象棋机器人系统..."
echo "=========================="

# 检查是否为第一次运行
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "首次运行，正在设置系统..."
    "$SCRIPT_DIR/scripts/deploy.sh" deploy
else
    echo "启动现有系统..."
    "$SCRIPT_DIR/scripts/deploy.sh" start
fi

echo ""
echo "✅ 系统启动完成！"
echo ""
echo "访问地址:"
echo "  前端界面: http://localhost:3000"
echo "  API文档:  http://localhost:8000/docs"
echo "  Redis管理: http://localhost:8001 (如果启用)"
echo ""
echo "常用命令:"
echo "  查看状态: ./scripts/deploy.sh status"
echo "  查看日志: ./scripts/deploy.sh logs"
echo "  停止系统: ./scripts/deploy.sh stop"
echo "  查看帮助: ./scripts/deploy.sh help"
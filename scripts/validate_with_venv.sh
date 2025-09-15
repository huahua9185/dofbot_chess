#!/bin/bash
# 在虚拟环境中验证项目设置

set -e

PROJECT_ROOT="/home/jetson/prog"
cd $PROJECT_ROOT

echo "=== 在虚拟环境中运行项目验证 ==="

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "已激活虚拟环境"
else
    echo "错误：虚拟环境不存在"
    exit 1
fi

# 运行验证脚本
python scripts/validate_setup.py
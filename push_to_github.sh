#!/bin/bash

# GitHub推送脚本
# 使用Personal Access Token进行认证推送

set -e

echo "🚀 象棋机器人项目 - GitHub推送脚本"
echo "=================================="
echo ""

# 显示当前状态
echo "📊 当前Git状态:"
git status --short
echo ""

echo "📝 最近的提交:"
git log --oneline -3
echo ""

echo "📡 远程仓库:"
git remote -v
echo ""

# 检查是否有待推送的提交
COMMITS_AHEAD=$(git rev-list --count origin/main..main 2>/dev/null || echo "0")
if [ "$COMMITS_AHEAD" -eq "0" ]; then
    echo "✅ 没有新的提交需要推送"
    exit 0
fi

echo "📤 有 $COMMITS_AHEAD 个提交待推送到远程仓库"
echo ""

# 提示用户输入token
echo "🔐 需要GitHub Personal Access Token进行认证"
echo ""
echo "如何获取Personal Access Token:"
echo "1. 访问 GitHub.com > Settings > Developer settings > Personal access tokens > Tokens (classic)"
echo "2. 点击 'Generate new token (classic)'"
echo "3. 选择 'repo' 权限"
echo "4. 复制生成的token"
echo ""

read -s -p "请输入您的GitHub Personal Access Token: " TOKEN
echo ""

if [ -z "$TOKEN" ]; then
    echo "❌ Token不能为空"
    exit 1
fi

# 构建认证URL
USERNAME=$(git config user.name)
if [ -z "$USERNAME" ]; then
    read -p "请输入GitHub用户名: " USERNAME
fi

REPO_URL="https://${USERNAME}:${TOKEN}@github.com/huahua9185/dofbot_chess.git"

echo ""
echo "🔄 正在推送到远程仓库..."

# 临时设置远程URL并推送
git remote set-url origin "$REPO_URL"

if git push origin main; then
    echo ""
    echo "✅ 成功推送到GitHub!"
    echo "🌐 仓库地址: https://github.com/huahua9185/dofbot_chess"

    # 恢复原始URL (移除token)
    git remote set-url origin "https://github.com/huahua9185/dofbot_chess.git"

    echo ""
    echo "📋 推送的内容包括:"
    echo "- Docker容器化部署配置"
    echo "- 自动化部署脚本"
    echo "- 完整的微服务架构"
    echo "- MongoDB和Redis数据存储"
    echo "- React前端界面和3D棋盘"
    echo "- 详细的部署文档"

else
    echo ""
    echo "❌ 推送失败"
    # 恢复原始URL
    git remote set-url origin "https://github.com/huahua9185/dofbot_chess.git"
    exit 1
fi
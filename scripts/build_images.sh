#!/bin/bash

# 象棋机器人系统 - Docker镜像构建脚本
# 作者: 象棋机器人开发团队

set -e  # 遇到错误时停止

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

echo "🤖 象棋机器人系统 - Docker镜像构建脚本"
echo "================================"

# 服务列表
SERVICES=(
    "web-gateway:services/web_gateway/Dockerfile"
    "game-manager:services/game_manager/Dockerfile"
    "ai-engine:services/ai_service/Dockerfile"
    "vision-service:services/vision_service/Dockerfile"
    "robot-service:services/robot_service/Dockerfile"
)

# 构建函数
build_service() {
    local service_name=$1
    local dockerfile_path=$2

    log_info "构建 ${service_name} 服务镜像..."

    if docker build -t chess-robot/${service_name}:latest -f ${dockerfile_path} . > /tmp/build_${service_name}.log 2>&1; then
        log_info "✅ ${service_name} 镜像构建成功"
        return 0
    else
        log_error "❌ ${service_name} 镜像构建失败"
        log_error "详细日志请查看: /tmp/build_${service_name}.log"
        tail -20 /tmp/build_${service_name}.log
        return 1
    fi
}

# 主构建流程
main() {
    local build_all=true
    local specific_service=""

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --service)
                specific_service="$2"
                build_all=false
                shift 2
                ;;
            --all)
                build_all=true
                shift
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo "选项:"
                echo "  --service NAME    只构建指定服务"
                echo "  --all            构建所有服务 (默认)"
                echo "  --help, -h       显示帮助信息"
                echo ""
                echo "可用服务: web-gateway, game-manager, ai-engine, vision-service, robot-service"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                exit 1
                ;;
        esac
    done

    # 检查Docker是否运行
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 未运行，请先启动 Docker"
        exit 1
    fi

    log_info "开始构建镜像..."

    local success_count=0
    local total_count=0

    if [[ "$build_all" == true ]]; then
        # 构建所有服务
        for service in "${SERVICES[@]}"; do
            IFS=':' read -r name dockerfile <<< "$service"
            total_count=$((total_count + 1))

            if build_service "$name" "$dockerfile"; then
                success_count=$((success_count + 1))
            fi
        done
    else
        # 构建指定服务
        found=false
        for service in "${SERVICES[@]}"; do
            IFS=':' read -r name dockerfile <<< "$service"
            if [[ "$name" == "$specific_service" ]]; then
                found=true
                total_count=1
                if build_service "$name" "$dockerfile"; then
                    success_count=1
                fi
                break
            fi
        done

        if [[ "$found" == false ]]; then
            log_error "未找到服务: $specific_service"
            log_info "可用服务: $(echo "${SERVICES[@]}" | sed 's/:[^ ]*//g')"
            exit 1
        fi
    fi

    echo ""
    log_info "构建完成: $success_count/$total_count 个服务构建成功"

    if [[ $success_count -eq $total_count ]]; then
        log_info "🎉 所有镜像构建成功！"

        # 显示构建的镜像
        echo ""
        log_info "构建的镜像列表:"
        docker images | grep chess-robot | head -10

        exit 0
    else
        log_error "部分镜像构建失败，请检查日志"
        exit 1
    fi
}

# 执行主函数
main "$@"
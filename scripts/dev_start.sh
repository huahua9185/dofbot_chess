#!/bin/bash

# 象棋机器人系统 - 开发环境快速启动脚本
# 作者: 象棋机器人开发团队

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
PROJECT_ROOT="/home/jetson/prog"
COMPOSE_FILE="docker-compose.dev.yml"
SIMPLE_COMPOSE_FILE="docker-compose.simple.yml"

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

# 显示帮助信息
show_help() {
    echo "🤖 象棋机器人系统 - 开发环境快速启动脚本"
    echo "================================"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  start          启动开发环境"
    echo "  stop           停止开发环境"
    echo "  restart        重启开发环境"
    echo "  status         查看服务状态"
    echo "  logs           查看服务日志"
    echo "  build          构建镜像"
    echo "  clean          清理环境"
    echo "  health         检查服务健康状态"
    echo "  help           显示帮助信息"
    echo ""
    echo "选项:"
    echo "  --service NAME 指定特定服务"
    echo "  --rebuild      强制重新构建镜像"
    echo "  --no-deps      不启动依赖服务"
    echo "  --follow       跟踪日志输出"
    echo ""
    echo "示例:"
    echo "  $0 start                    # 启动所有服务"
    echo "  $0 start --rebuild          # 重新构建并启动"
    echo "  $0 logs --service web       # 查看web服务日志"
    echo "  $0 status                   # 查看所有服务状态"
}

# 检查环境
check_environment() {
    log_info "检查开发环境..."

    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi

    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 未运行，请先启动 Docker"
        exit 1
    fi

    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi

    # 检查项目目录
    if [[ ! -d "$PROJECT_ROOT" ]]; then
        log_error "项目目录不存在: $PROJECT_ROOT"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    # 检查compose文件
    if [[ ! -f "$SIMPLE_COMPOSE_FILE" ]]; then
        log_error "Compose文件不存在: $SIMPLE_COMPOSE_FILE"
        exit 1
    fi

    log_info "环境检查通过"
}

# 构建镜像
build_images() {
    local rebuild_flag=${1:-false}
    local specific_service=${2:-""}

    log_info "构建Docker镜像..."

    if [[ "$rebuild_flag" == true ]]; then
        log_info "强制重新构建镜像..."
        docker-compose -f "$SIMPLE_COMPOSE_FILE" build --no-cache
    else
        # 检查是否需要构建
        local needs_build=false

        if [[ -n "$specific_service" ]]; then
            if ! docker images | grep -q "chess-robot/$specific_service"; then
                needs_build=true
            fi
        else
            # 检查所有服务镜像
            for service in web-gateway game-manager ai-engine; do
                if ! docker images | grep -q "chess-robot/$service"; then
                    needs_build=true
                    break
                fi
            done
        fi

        if [[ "$needs_build" == true ]]; then
            log_info "检测到缺失的镜像，开始构建..."
            if [[ -f "scripts/build_images.sh" ]]; then
                if [[ -n "$specific_service" ]]; then
                    ./scripts/build_images.sh --service "$specific_service"
                else
                    ./scripts/build_images.sh --all
                fi
            else
                docker-compose -f "$SIMPLE_COMPOSE_FILE" build
            fi
        else
            log_info "所有镜像已存在，跳过构建"
        fi
    fi
}

# 启动服务
start_services() {
    local rebuild=${1:-false}
    local specific_service=${2:-""}

    log_info "启动开发环境..."

    # 停止可能冲突的本地服务
    log_debug "检查并停止冲突的本地服务..."
    sudo systemctl stop redis-server 2>/dev/null || true
    sudo systemctl stop mongodb 2>/dev/null || true

    # 构建镜像（如果需要）
    build_images "$rebuild" "$specific_service"

    # 启动服务
    if [[ -n "$specific_service" ]]; then
        log_info "启动服务: $specific_service"
        docker-compose -f "$SIMPLE_COMPOSE_FILE" up -d "$specific_service"
    else
        log_info "启动所有服务..."
        docker-compose -f "$SIMPLE_COMPOSE_FILE" up -d
    fi

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 5

    # 显示状态
    show_status
}

# 停止服务
stop_services() {
    local specific_service=${1:-""}

    log_info "停止开发环境..."

    if [[ -n "$specific_service" ]]; then
        log_info "停止服务: $specific_service"
        docker-compose -f "$SIMPLE_COMPOSE_FILE" stop "$specific_service"
    else
        docker-compose -f "$SIMPLE_COMPOSE_FILE" down
    fi

    log_info "服务已停止"
}

# 重启服务
restart_services() {
    local rebuild=${1:-false}
    local specific_service=${2:-""}

    log_info "重启开发环境..."
    stop_services "$specific_service"
    sleep 2
    start_services "$rebuild" "$specific_service"
}

# 显示状态
show_status() {
    log_info "服务状态:"
    echo ""
    docker-compose -f "$SIMPLE_COMPOSE_FILE" ps
    echo ""

    # 显示端口映射
    log_info "端口映射:"
    echo "  Web网关:    http://localhost:8000"
    echo "  MongoDB:    localhost:27017"
    echo "  Redis:      localhost:6379"
    echo ""

    # 显示运行中的容器
    local running_containers=$(docker ps --filter "name=chess_robot" --format "{{.Names}}" | wc -l)
    if [[ $running_containers -gt 0 ]]; then
        log_info "运行中的服务: $running_containers 个"
        docker ps --filter "name=chess_robot" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        log_warn "没有运行中的服务"
    fi
}

# 查看日志
show_logs() {
    local specific_service=${1:-""}
    local follow_flag=${2:-false}

    if [[ -n "$specific_service" ]]; then
        log_info "查看 $specific_service 服务日志:"
        if [[ "$follow_flag" == true ]]; then
            docker-compose -f "$SIMPLE_COMPOSE_FILE" logs -f "$specific_service"
        else
            docker-compose -f "$SIMPLE_COMPOSE_FILE" logs --tail=50 "$specific_service"
        fi
    else
        log_info "查看所有服务日志:"
        if [[ "$follow_flag" == true ]]; then
            docker-compose -f "$SIMPLE_COMPOSE_FILE" logs -f
        else
            docker-compose -f "$SIMPLE_COMPOSE_FILE" logs --tail=20
        fi
    fi
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    # 检查Web服务
    if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
        log_info "✅ Web网关服务: 正常"
    else
        log_warn "❌ Web网关服务: 异常"
    fi

    # 检查Redis
    if docker exec chess_robot_redis redis-cli ping 2>/dev/null | grep -q PONG; then
        log_info "✅ Redis服务: 正常"
    else
        log_warn "❌ Redis服务: 异常"
    fi

    # 检查MongoDB
    if docker exec chess_robot_mongodb mongosh --eval "db.runCommand('ping')" 2>/dev/null | grep -q ok; then
        log_info "✅ MongoDB服务: 正常"
    else
        log_warn "❌ MongoDB服务: 异常"
    fi

    echo ""
    show_status
}

# 清理环境
clean_environment() {
    log_warn "清理开发环境..."

    # 停止所有服务
    docker-compose -f "$SIMPLE_COMPOSE_FILE" down

    # 删除未使用的镜像和容器
    log_info "清理未使用的Docker资源..."
    docker system prune -f

    log_info "环境清理完成"
}

# 主函数
main() {
    local command=""
    local rebuild=false
    local specific_service=""
    local follow_logs=false
    local no_deps=false

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            start|stop|restart|status|logs|build|clean|health|help)
                command="$1"
                shift
                ;;
            --service)
                specific_service="$2"
                shift 2
                ;;
            --rebuild)
                rebuild=true
                shift
                ;;
            --follow)
                follow_logs=true
                shift
                ;;
            --no-deps)
                no_deps=true
                shift
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 如果没有指定命令，显示帮助
    if [[ -z "$command" ]]; then
        show_help
        exit 0
    fi

    # 显示标题
    echo "🤖 象棋机器人系统 - 开发环境管理"
    echo "================================"

    # 检查环境（除了help命令）
    if [[ "$command" != "help" ]]; then
        check_environment
    fi

    # 执行命令
    case $command in
        start)
            start_services "$rebuild" "$specific_service"
            ;;
        stop)
            stop_services "$specific_service"
            ;;
        restart)
            restart_services "$rebuild" "$specific_service"
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$specific_service" "$follow_logs"
            ;;
        build)
            build_images true "$specific_service"
            ;;
        clean)
            clean_environment
            ;;
        health)
            health_check
            ;;
        help)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@"
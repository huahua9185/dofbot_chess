#!/bin/bash

# 象棋机器人系统部署脚本
# 支持生产环境、开发环境和仅硬件环境的部署

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色输出
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

# 显示帮助信息
show_help() {
    echo "象棋机器人系统部署脚本"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  deploy          部署完整系统"
    echo "  deploy-dev      部署开发环境"
    echo "  deploy-hw       部署硬件环境 (包含摄像头和机械臂)"
    echo "  start           启动系统"
    echo "  stop            停止系统"
    echo "  restart         重启系统"
    echo "  status          查看系统状态"
    echo "  logs            查看日志"
    echo "  build           构建Docker镜像"
    echo "  clean           清理系统"
    echo "  backup          备份数据"
    echo "  restore         恢复数据"
    echo "  test            运行测试"
    echo "  help            显示帮助信息"
    echo ""
    echo "选项:"
    echo "  --env-file      指定环境变量文件 (默认: .env)"
    echo "  --compose-file  指定Docker Compose文件"
    echo "  --service       指定特定服务"
    echo "  --no-build      跳过镜像构建"
    echo "  --force         强制执行"
    echo ""
    echo "示例:"
    echo "  $0 deploy                    # 部署生产环境"
    echo "  $0 deploy-dev                # 部署开发环境"
    echo "  $0 deploy-hw                 # 部署硬件环境"
    echo "  $0 start --service web-ui    # 只启动前端服务"
    echo "  $0 logs --service mongodb    # 查看MongoDB日志"
    echo "  $0 test --service ai-engine  # 测试AI引擎服务"
}

# 检查系统依赖
check_dependencies() {
    log_info "检查系统依赖..."

    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi

    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi

    # 检查Docker服务状态
    if ! systemctl is-active --quiet docker; then
        log_info "启动Docker服务..."
        sudo systemctl start docker
        sudo systemctl enable docker
    fi

    log_info "系统依赖检查通过"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."

    mkdir -p "$PROJECT_ROOT/data/mongodb"
    mkdir -p "$PROJECT_ROOT/data/redis"
    mkdir -p "$PROJECT_ROOT/data/calibration"
    mkdir -p "$PROJECT_ROOT/data/logs"
    mkdir -p "$PROJECT_ROOT/data/backups"
    mkdir -p "$PROJECT_ROOT/data/uploads"

    # 设置权限
    chmod 755 "$PROJECT_ROOT/data"
    chmod -R 755 "$PROJECT_ROOT/data"

    log_info "目录创建完成"
}

# 构建Docker镜像
build_images() {
    local skip_build=${1:-false}

    if [ "$skip_build" = true ]; then
        log_info "跳过Docker镜像构建"
        return 0
    fi

    log_info "构建Docker镜像..."

    cd "$PROJECT_ROOT"

    # 构建各个服务的镜像
    log_debug "构建Web网关服务镜像..."
    docker build -t chess-robot/web-gateway:latest -f services/web_gateway/Dockerfile .

    log_debug "构建游戏管理服务镜像..."
    docker build -t chess-robot/game-manager:latest -f services/game_manager/Dockerfile .

    log_debug "构建AI引擎服务镜像..."
    docker build -t chess-robot/ai-engine:latest -f services/ai_service/Dockerfile .

    log_debug "构建视觉识别服务镜像..."
    docker build -t chess-robot/vision-service:latest -f services/vision_service/Dockerfile .

    log_debug "构建机器人控制服务镜像..."
    docker build -t chess-robot/robot-service:latest -f services/robot_service/Dockerfile .

    log_debug "构建前端应用镜像..."
    docker build -t chess-robot/web-ui:latest -f web_ui/Dockerfile .

    log_info "Docker镜像构建完成"
}

# 部署系统
deploy_system() {
    local env_file="${1:-$PROJECT_ROOT/.env}"
    local compose_file="${2:-$PROJECT_ROOT/docker-compose.yml}"
    local profile="${3:-}"
    local skip_build="${4:-false}"

    log_info "开始部署系统..."

    # 检查依赖
    check_dependencies

    # 创建目录
    create_directories

    # 构建镜像
    build_images "$skip_build"

    # 停止现有服务
    stop_system "$env_file" "$compose_file" true

    cd "$PROJECT_ROOT"

    # 启动服务
    local docker_compose_cmd="docker-compose --env-file $env_file -f $compose_file"

    if [ -n "$profile" ]; then
        docker_compose_cmd="$docker_compose_cmd --profile $profile"
    fi

    log_info "启动服务..."
    $docker_compose_cmd up -d

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 30

    # 检查服务状态
    check_services_health "$env_file" "$compose_file"

    log_info "系统部署完成"
}

# 检查服务健康状态
check_services_health() {
    local env_file="${1:-$PROJECT_ROOT/.env}"
    local compose_file="${2:-$PROJECT_ROOT/docker-compose.yml}"

    log_info "检查服务健康状态..."

    cd "$PROJECT_ROOT"

    # 获取服务状态
    local services_status=$(docker-compose --env-file "$env_file" -f "$compose_file" ps --format "table {{.Name}}\t{{.Status}}")

    echo "$services_status"

    # 检查关键服务
    local critical_services=("mongodb" "redis" "web-gateway")

    for service in "${critical_services[@]}"; do
        if docker-compose --env-file "$env_file" -f "$compose_file" ps "$service" | grep -q "Up"; then
            log_info "$service 服务运行正常"
        else
            log_error "$service 服务启动失败"
            # 显示服务日志
            docker-compose --env-file "$env_file" -f "$compose_file" logs --tail 20 "$service"
        fi
    done
}

# 启动系统
start_system() {
    local env_file="${1:-$PROJECT_ROOT/.env}"
    local compose_file="${2:-$PROJECT_ROOT/docker-compose.yml}"
    local service="${3:-}"

    log_info "启动系统..."

    cd "$PROJECT_ROOT"

    local docker_compose_cmd="docker-compose --env-file $env_file -f $compose_file"

    if [ -n "$service" ]; then
        $docker_compose_cmd start "$service"
        log_info "服务 $service 启动完成"
    else
        $docker_compose_cmd start
        log_info "所有服务启动完成"
    fi
}

# 停止系统
stop_system() {
    local env_file="${1:-$PROJECT_ROOT/.env}"
    local compose_file="${2:-$PROJECT_ROOT/docker-compose.yml}"
    local quiet="${3:-false}"

    if [ "$quiet" != true ]; then
        log_info "停止系统..."
    fi

    cd "$PROJECT_ROOT"

    docker-compose --env-file "$env_file" -f "$compose_file" down

    if [ "$quiet" != true ]; then
        log_info "系统停止完成"
    fi
}

# 重启系统
restart_system() {
    local env_file="${1:-$PROJECT_ROOT/.env}"
    local compose_file="${2:-$PROJECT_ROOT/docker-compose.yml}"
    local service="${3:-}"

    log_info "重启系统..."

    stop_system "$env_file" "$compose_file" true
    sleep 5
    start_system "$env_file" "$compose_file" "$service"

    log_info "系统重启完成"
}

# 查看系统状态
show_status() {
    local env_file="${1:-$PROJECT_ROOT/.env}"
    local compose_file="${2:-$PROJECT_ROOT/docker-compose.yml}"

    log_info "系统状态:"

    cd "$PROJECT_ROOT"

    # 显示服务状态
    docker-compose --env-file "$env_file" -f "$compose_file" ps

    # 显示资源使用情况
    echo ""
    log_info "容器资源使用情况:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

    # 显示磁盘使用情况
    echo ""
    log_info "数据目录磁盘使用情况:"
    du -sh "$PROJECT_ROOT/data"/* 2>/dev/null || echo "无数据目录"
}

# 查看日志
show_logs() {
    local env_file="${1:-$PROJECT_ROOT/.env}"
    local compose_file="${2:-$PROJECT_ROOT/docker-compose.yml}"
    local service="${3:-}"
    local lines="${4:-100}"

    cd "$PROJECT_ROOT"

    if [ -n "$service" ]; then
        log_info "查看 $service 服务日志 (最近 $lines 行):"
        docker-compose --env-file "$env_file" -f "$compose_file" logs --tail "$lines" -f "$service"
    else
        log_info "查看所有服务日志 (最近 $lines 行):"
        docker-compose --env-file "$env_file" -f "$compose_file" logs --tail "$lines" -f
    fi
}

# 清理系统
clean_system() {
    local force="${1:-false}"

    if [ "$force" != true ]; then
        log_warn "这将删除所有容器、镜像和数据。确定要继续吗? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "操作已取消"
            return 0
        fi
    fi

    log_info "清理系统..."

    cd "$PROJECT_ROOT"

    # 停止并删除容器
    docker-compose -f docker-compose.yml down -v --remove-orphans
    docker-compose -f docker-compose.dev.yml down -v --remove-orphans 2>/dev/null || true

    # 删除镜像
    docker rmi $(docker images -q chess-robot/* 2>/dev/null) 2>/dev/null || true

    # 清理未使用的资源
    docker system prune -f

    # 清理数据目录
    if [ -d "$PROJECT_ROOT/data" ]; then
        sudo rm -rf "$PROJECT_ROOT/data"/*
    fi

    log_info "系统清理完成"
}

# 备份数据
backup_system() {
    local backup_name="${1:-$(date +%Y%m%d_%H%M%S)}"
    local backup_dir="$PROJECT_ROOT/data/backups/$backup_name"

    log_info "开始备份系统数据..."

    mkdir -p "$backup_dir"

    # 备份MongoDB
    if docker ps | grep -q chess_robot_mongodb; then
        log_debug "备份MongoDB数据..."
        docker exec chess_robot_mongodb mongodump --out /tmp/backup
        docker cp chess_robot_mongodb:/tmp/backup "$backup_dir/mongodb"
    fi

    # 备份Redis
    if docker ps | grep -q chess_robot_redis; then
        log_debug "备份Redis数据..."
        docker exec chess_robot_redis redis-cli BGSAVE
        sleep 5
        docker cp chess_robot_redis:/data/dump.rdb "$backup_dir/redis_dump.rdb"
    fi

    # 备份配置文件
    log_debug "备份配置文件..."
    cp -r "$PROJECT_ROOT/infrastructure/configs" "$backup_dir/"
    cp "$PROJECT_ROOT/.env" "$backup_dir/" 2>/dev/null || true
    cp "$PROJECT_ROOT/.env.dev" "$backup_dir/" 2>/dev/null || true

    # 压缩备份
    cd "$PROJECT_ROOT/data/backups"
    tar -czf "${backup_name}.tar.gz" "$backup_name"
    rm -rf "$backup_name"

    log_info "备份完成: $PROJECT_ROOT/data/backups/${backup_name}.tar.gz"
}

# 运行测试
run_tests() {
    local service="${1:-}"

    log_info "运行测试..."

    cd "$PROJECT_ROOT"

    if [ -n "$service" ]; then
        log_info "运行 $service 服务测试..."
        # 根据服务运行特定测试
        case "$service" in
            "web-gateway")
                python -m pytest services/web_gateway/tests/ -v
                ;;
            "ai-engine")
                python -m pytest services/ai_service/tests/ -v
                ;;
            "game-manager")
                python -m pytest services/game_manager/tests/ -v
                ;;
            "vision-service")
                python -m pytest services/vision_service/tests/ -v
                ;;
            "robot-service")
                python -m pytest services/robot_service/tests/ -v
                ;;
            *)
                log_error "未知的服务: $service"
                exit 1
                ;;
        esac
    else
        log_info "运行所有测试..."
        python -m pytest -v

        # 运行前端测试
        cd web_ui
        npm test -- --coverage --watchAll=false
    fi

    log_info "测试完成"
}

# 解析命令行参数
parse_args() {
    local command=""
    local env_file="$PROJECT_ROOT/.env"
    local compose_file=""
    local service=""
    local skip_build=false
    local force=false
    local lines=100

    while [[ $# -gt 0 ]]; do
        case $1 in
            deploy|deploy-dev|deploy-hw|start|stop|restart|status|logs|build|clean|backup|restore|test|help)
                command="$1"
                shift
                ;;
            --env-file)
                env_file="$2"
                shift 2
                ;;
            --compose-file)
                compose_file="$2"
                shift 2
                ;;
            --service)
                service="$2"
                shift 2
                ;;
            --no-build)
                skip_build=true
                shift
                ;;
            --force)
                force=true
                shift
                ;;
            --lines)
                lines="$2"
                shift 2
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 根据命令设置默认compose文件
    if [ -z "$compose_file" ]; then
        case "$command" in
            "deploy-dev")
                compose_file="$PROJECT_ROOT/docker-compose.dev.yml"
                ;;
            "deploy-hw")
                compose_file="$PROJECT_ROOT/docker-compose.yml"
                ;;
            *)
                compose_file="$PROJECT_ROOT/docker-compose.yml"
                ;;
        esac
    fi

    # 执行命令
    case "$command" in
        "deploy")
            deploy_system "$env_file" "$compose_file" "" "$skip_build"
            ;;
        "deploy-dev")
            env_file="${env_file/.env/.env.dev}"
            deploy_system "$env_file" "$compose_file" "" "$skip_build"
            ;;
        "deploy-hw")
            deploy_system "$env_file" "$compose_file" "hardware" "$skip_build"
            ;;
        "start")
            start_system "$env_file" "$compose_file" "$service"
            ;;
        "stop")
            stop_system "$env_file" "$compose_file"
            ;;
        "restart")
            restart_system "$env_file" "$compose_file" "$service"
            ;;
        "status")
            show_status "$env_file" "$compose_file"
            ;;
        "logs")
            show_logs "$env_file" "$compose_file" "$service" "$lines"
            ;;
        "build")
            build_images "$skip_build"
            ;;
        "clean")
            clean_system "$force"
            ;;
        "backup")
            backup_system
            ;;
        "test")
            run_tests "$service"
            ;;
        "help"|"")
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 主函数
main() {
    echo "🤖 象棋机器人系统部署脚本"
    echo "================================"

    parse_args "$@"
}

# 执行主函数
main "$@"
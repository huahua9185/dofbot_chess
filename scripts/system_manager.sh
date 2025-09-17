#!/bin/bash

# 象棋机器人系统 - 统一管理脚本
# 作者: 象棋机器人开发团队

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 配置
PROJECT_ROOT="/home/jetson/prog"
ENVIRONMENTS=("dev" "prod" "monitoring")

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

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 显示横幅
show_banner() {
    echo -e "${CYAN}"
    echo "🤖 象棋机器人系统管理中心"
    echo "================================"
    echo "版本: 1.0.0"
    echo "环境: $(uname -n)"
    echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${NC}"
}

# 显示帮助信息
show_help() {
    show_banner
    echo ""
    echo "用法: $0 [环境] [命令] [选项]"
    echo ""
    echo "环境:"
    echo "  dev            开发环境"
    echo "  prod           生产环境"
    echo "  monitoring     监控环境"
    echo ""
    echo "命令:"
    echo "  start          启动环境"
    echo "  stop           停止环境"
    echo "  restart        重启环境"
    echo "  status         查看状态"
    echo "  logs           查看日志"
    echo "  build          构建镜像"
    echo "  clean          清理环境"
    echo "  health         健康检查"
    echo "  backup         备份数据"
    echo "  restore        恢复数据"
    echo "  deploy         部署系统"
    echo "  update         更新系统"
    echo ""
    echo "全局命令:"
    echo "  init           初始化系统"
    echo "  check          系统检查"
    echo "  monitor        实时监控"
    echo "  dashboard      打开仪表板"
    echo ""
    echo "选项:"
    echo "  --service NAME 指定服务"
    echo "  --follow       跟踪日志"
    echo "  --force        强制执行"
    echo "  --dry-run      预览操作"
    echo ""
    echo "示例:"
    echo "  $0 dev start                    # 启动开发环境"
    echo "  $0 prod deploy --force          # 强制部署生产环境"
    echo "  $0 monitoring start             # 启动监控系统"
    echo "  $0 check                        # 系统检查"
    echo "  $0 dev logs --service web       # 查看开发环境web服务日志"
}

# 检查环境
check_environment() {
    log_info "检查系统环境..."

    # 检查基础工具
    local required_tools=("docker" "docker-compose" "curl" "jq")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "缺少必要工具: $tool"
            return 1
        fi
    done

    # 检查Docker状态
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 未运行"
        return 1
    fi

    # 检查项目目录
    if [[ ! -d "$PROJECT_ROOT" ]]; then
        log_error "项目目录不存在: $PROJECT_ROOT"
        return 1
    fi

    cd "$PROJECT_ROOT"

    log_success "环境检查通过"
    return 0
}

# 获取Compose文件
get_compose_file() {
    local env=$1
    case $env in
        dev)
            echo "docker-compose.simple.yml"
            ;;
        prod)
            echo "docker-compose.prod.yml"
            ;;
        monitoring)
            echo "docker-compose.monitoring.yml"
            ;;
        *)
            log_error "未知环境: $env"
            return 1
            ;;
    esac
}

# 启动环境
start_environment() {
    local env=$1
    local service=$2
    local force=$3

    log_info "启动 $env 环境..."

    local compose_file=$(get_compose_file "$env")
    if [[ ! -f "$compose_file" ]]; then
        log_error "Compose文件不存在: $compose_file"
        return 1
    fi

    # 停止冲突服务
    if [[ "$env" == "dev" || "$env" == "prod" ]]; then
        sudo systemctl stop redis-server 2>/dev/null || true
        sudo systemctl stop mongodb 2>/dev/null || true
    fi

    # 启动服务
    if [[ -n "$service" ]]; then
        log_info "启动服务: $service"
        docker-compose -f "$compose_file" up -d "$service"
    else
        log_info "启动所有服务"
        docker-compose -f "$compose_file" up -d
    fi

    # 等待服务启动
    sleep 5
    show_status "$env"
}

# 停止环境
stop_environment() {
    local env=$1
    local service=$2

    log_info "停止 $env 环境..."

    local compose_file=$(get_compose_file "$env")
    if [[ ! -f "$compose_file" ]]; then
        log_error "Compose文件不存在: $compose_file"
        return 1
    fi

    if [[ -n "$service" ]]; then
        log_info "停止服务: $service"
        docker-compose -f "$compose_file" stop "$service"
    else
        docker-compose -f "$compose_file" down
    fi

    log_success "$env 环境已停止"
}

# 显示状态
show_status() {
    local env=$1

    log_info "$env 环境状态:"
    echo ""

    local compose_file=$(get_compose_file "$env")
    if [[ -f "$compose_file" ]]; then
        docker-compose -f "$compose_file" ps
    fi

    echo ""
    log_info "系统资源使用:"
    echo "  CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')%"
    echo "  内存: $(free | awk 'NR==2{printf "%.1f%%", $3*100/$2}')"
    echo "  磁盘: $(df -h / | awk 'NR==2{print $5}')"
}

# 查看日志
show_logs() {
    local env=$1
    local service=$2
    local follow=$3

    local compose_file=$(get_compose_file "$env")
    if [[ ! -f "$compose_file" ]]; then
        log_error "Compose文件不存在: $compose_file"
        return 1
    fi

    if [[ -n "$service" ]]; then
        log_info "查看 $env 环境 $service 服务日志:"
        if [[ "$follow" == true ]]; then
            docker-compose -f "$compose_file" logs -f "$service"
        else
            docker-compose -f "$compose_file" logs --tail=50 "$service"
        fi
    else
        log_info "查看 $env 环境所有服务日志:"
        if [[ "$follow" == true ]]; then
            docker-compose -f "$compose_file" logs -f
        else
            docker-compose -f "$compose_file" logs --tail=20
        fi
    fi
}

# 构建镜像
build_images() {
    local service=$1
    local force=$2

    log_info "构建Docker镜像..."

    if [[ -f "scripts/build_images.sh" ]]; then
        if [[ -n "$service" ]]; then
            ./scripts/build_images.sh --service "$service"
        else
            ./scripts/build_images.sh --all
        fi
    else
        log_error "构建脚本不存在: scripts/build_images.sh"
        return 1
    fi
}

# 健康检查
health_check() {
    local env=$1

    if [[ -f "scripts/health_check.sh" ]]; then
        log_info "执行 $env 环境健康检查..."
        ./scripts/health_check.sh check
    else
        log_error "健康检查脚本不存在: scripts/health_check.sh"
        return 1
    fi
}

# 系统初始化
system_init() {
    log_info "初始化象棋机器人系统..."

    # 创建必要目录
    mkdir -p data/{logs,mongodb,redis,games,models,calibration}
    mkdir -p monitoring/{prometheus,grafana,alertmanager}

    # 设置权限
    chmod +x scripts/*.sh

    # 构建镜像
    build_images

    log_success "系统初始化完成"
}

# 打开仪表板
open_dashboard() {
    local env=$1

    case $env in
        dev)
            log_info "开发环境仪表板:"
            echo "  Web界面: http://localhost:8000"
            echo "  API文档: http://localhost:8000/docs"
            ;;
        prod)
            log_info "生产环境仪表板:"
            echo "  Web界面: http://localhost"
            echo "  管理界面: http://localhost:8080"
            ;;
        monitoring)
            log_info "监控仪表板:"
            echo "  Grafana: http://localhost:3000 (admin/chess_robot_2024)"
            echo "  Prometheus: http://localhost:9090"
            echo "  AlertManager: http://localhost:9093"
            ;;
    esac
}

# 实时监控
real_time_monitor() {
    log_info "进入实时监控模式 (按 Ctrl+C 退出)..."

    if [[ -f "scripts/health_check.sh" ]]; then
        ./scripts/health_check.sh monitor --interval 10
    else
        log_error "健康检查脚本不存在"
        return 1
    fi
}

# 主函数
main() {
    local environment=""
    local command=""
    local service=""
    local follow=false
    local force=false
    local dry_run=false

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            dev|prod|monitoring)
                environment="$1"
                shift
                ;;
            start|stop|restart|status|logs|build|clean|health|backup|restore|deploy|update)
                command="$1"
                shift
                ;;
            init|check|monitor|dashboard|help)
                command="$1"
                shift
                ;;
            --service)
                service="$2"
                shift 2
                ;;
            --follow)
                follow=true
                shift
                ;;
            --force)
                force=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 显示横幅
    show_banner

    # 如果没有指定命令，显示帮助
    if [[ -z "$command" ]]; then
        show_help
        exit 0
    fi

    # 全局命令（不需要环境参数）
    case $command in
        help)
            show_help
            exit 0
            ;;
        init)
            check_environment && system_init
            exit $?
            ;;
        check)
            check_environment
            exit $?
            ;;
        monitor)
            check_environment && real_time_monitor
            exit $?
            ;;
    esac

    # 需要环境参数的命令
    if [[ -z "$environment" ]]; then
        log_error "请指定环境: dev, prod, monitoring"
        echo "使用 '$0 help' 查看帮助"
        exit 1
    fi

    # 检查环境
    if ! check_environment; then
        exit 1
    fi

    # 执行命令
    case $command in
        start)
            start_environment "$environment" "$service" "$force"
            ;;
        stop)
            stop_environment "$environment" "$service"
            ;;
        restart)
            stop_environment "$environment" "$service"
            sleep 2
            start_environment "$environment" "$service" "$force"
            ;;
        status)
            show_status "$environment"
            ;;
        logs)
            show_logs "$environment" "$service" "$follow"
            ;;
        build)
            build_images "$service" "$force"
            ;;
        health)
            health_check "$environment"
            ;;
        dashboard)
            open_dashboard "$environment"
            ;;
        *)
            log_error "环境 '$environment' 不支持命令 '$command'"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
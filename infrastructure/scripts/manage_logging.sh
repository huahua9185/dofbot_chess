#!/bin/bash

# 智能象棋机器人日志系统管理脚本
# 用于部署和管理ELK日志堆栈

set -e

# 配置变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOGGING_DIR="$PROJECT_ROOT/infrastructure/logging"
LOG_DIR="$PROJECT_ROOT/logs"

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

# 检查依赖
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

    # 检查可用内存（ELK需要至少2GB）
    MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$MEMORY_GB" -lt 2 ]; then
        log_warn "系统内存小于2GB，ELK堆栈可能无法正常运行"
        log_warn "建议在资源充足的环境中运行日志系统"
    fi

    log_info "依赖检查完成"
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."

    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"

    # 为Elasticsearch创建数据目录
    sudo mkdir -p /var/lib/elasticsearch
    sudo chown -R 1000:1000 /var/lib/elasticsearch

    log_info "目录创建完成"
}

# 配置系统参数
configure_system() {
    log_info "配置系统参数..."

    # 设置虚拟内存映射计数（Elasticsearch需要）
    echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf > /dev/null
    sudo sysctl -p

    # 设置文件描述符限制
    echo '*               soft    nofile          65536' | sudo tee -a /etc/security/limits.conf > /dev/null
    echo '*               hard    nofile          65536' | sudo tee -a /etc/security/limits.conf > /dev/null

    log_info "系统参数配置完成"
}

# 部署日志系统
deploy_logging() {
    log_info "部署日志收集和分析系统..."

    cd "$LOGGING_DIR"

    # 拉取镜像
    log_info "拉取Docker镜像..."
    docker-compose -f docker-compose-logging.yml pull

    # 启动服务
    log_info "启动日志系统服务..."
    docker-compose -f docker-compose-logging.yml up -d

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 30

    # 检查服务状态
    check_services

    log_info "日志系统部署完成"
    log_info "Kibana界面: http://localhost:5601"
    log_info "日志分析API: http://localhost:8090"
    log_info "Fluent Bit状态: http://localhost:2020"
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."

    services=("elasticsearch" "kibana" "fluent-bit" "log_analyzer")

    for service in "${services[@]}"; do
        if docker ps | grep -q "chess_$service"; then
            log_info "✓ $service 运行中"
        else
            log_warn "✗ $service 未运行"
        fi
    done

    # 检查Elasticsearch健康状态
    if curl -s http://localhost:9200/_cluster/health > /dev/null; then
        log_info "✓ Elasticsearch 健康检查通过"
    else
        log_warn "✗ Elasticsearch 健康检查失败"
    fi

    # 检查Kibana状态
    if curl -s http://localhost:5601/api/status > /dev/null; then
        log_info "✓ Kibana 状态正常"
    else
        log_warn "✗ Kibana 状态异常"
    fi
}

# 停止日志系统
stop_logging() {
    log_info "停止日志系统..."

    cd "$LOGGING_DIR"
    docker-compose -f docker-compose-logging.yml stop

    log_info "日志系统已停止"
}

# 重启日志系统
restart_logging() {
    log_info "重启日志系统..."

    stop_logging
    sleep 5
    deploy_logging
}

# 清理日志系统
cleanup_logging() {
    log_info "清理日志系统..."

    cd "$LOGGING_DIR"

    # 停止并删除容器
    docker-compose -f docker-compose-logging.yml down -v

    # 删除镜像（可选）
    read -p "是否删除Docker镜像? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rmi $(docker images | grep -E "(elasticsearch|kibana|fluent)" | awk '{print $3}') 2>/dev/null || true
    fi

    log_info "日志系统清理完成"
}

# 查看日志
view_logs() {
    local service="${1:-}"

    if [ -z "$service" ]; then
        log_info "可用服务："
        docker ps --format "table {{.Names}}\t{{.Status}}" | grep chess_
        return
    fi

    log_info "显示 $service 的日志..."
    docker logs -f "chess_$service"
}

# 备份Elasticsearch数据
backup_elasticsearch() {
    log_info "备份Elasticsearch数据..."

    BACKUP_DIR="$PROJECT_ROOT/backups/elasticsearch/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # 创建快照仓库
    curl -X PUT "localhost:9200/_snapshot/backup_repository" -H 'Content-Type: application/json' -d '{
        "type": "fs",
        "settings": {
            "location": "/usr/share/elasticsearch/backup"
        }
    }'

    # 创建快照
    curl -X PUT "localhost:9200/_snapshot/backup_repository/backup_$(date +%Y%m%d_%H%M%S)" -H 'Content-Type: application/json' -d '{
        "indices": "chess-logs-*,chess-metrics-*",
        "ignore_unavailable": true,
        "include_global_state": false
    }'

    log_info "Elasticsearch数据备份完成：$BACKUP_DIR"
}

# 配置Kibana仪表板
setup_kibana_dashboards() {
    log_info "配置Kibana仪表板..."

    # 等待Kibana启动
    while ! curl -s http://localhost:5601/api/status > /dev/null; do
        log_info "等待Kibana启动..."
        sleep 10
    done

    # 创建索引模式
    curl -X POST "localhost:5601/api/saved_objects/index-pattern/chess-logs" \
        -H 'Content-Type: application/json' \
        -H 'kbn-xsrf: true' \
        -d '{
            "attributes": {
                "title": "chess-logs-*",
                "timeFieldName": "@timestamp"
            }
        }'

    curl -X POST "localhost:5601/api/saved_objects/index-pattern/chess-metrics" \
        -H 'Content-Type: application/json' \
        -H 'kbn-xsrf: true' \
        -d '{
            "attributes": {
                "title": "chess-metrics-*",
                "timeFieldName": "@timestamp"
            }
        }'

    log_info "Kibana仪表板配置完成"
}

# 显示系统信息
show_info() {
    log_info "=== 智能象棋机器人日志系统信息 ==="
    echo ""
    log_info "服务端点："
    echo "  - Elasticsearch: http://localhost:9200"
    echo "  - Kibana:        http://localhost:5601"
    echo "  - Fluent Bit:    http://localhost:2020"
    echo "  - 日志分析API:   http://localhost:8090"
    echo ""
    log_info "日志文件位置："
    echo "  - 本地日志目录: $LOG_DIR"
    echo "  - 配置文件:     $LOGGING_DIR"
    echo ""
    log_info "管理命令："
    echo "  - 查看日志:     $0 logs <service_name>"
    echo "  - 检查状态:     $0 status"
    echo "  - 重启系统:     $0 restart"
    echo ""
}

# 主函数
main() {
    local command="${1:-help}"

    case $command in
        "deploy")
            check_dependencies
            create_directories
            configure_system
            deploy_logging
            setup_kibana_dashboards
            show_info
            ;;
        "stop")
            stop_logging
            ;;
        "restart")
            restart_logging
            ;;
        "status")
            check_services
            ;;
        "cleanup")
            cleanup_logging
            ;;
        "logs")
            view_logs "$2"
            ;;
        "backup")
            backup_elasticsearch
            ;;
        "info")
            show_info
            ;;
        "help"|*)
            echo "智能象棋机器人日志系统管理脚本"
            echo ""
            echo "用法: $0 <command> [options]"
            echo ""
            echo "命令:"
            echo "  deploy      部署完整的日志系统"
            echo "  stop        停止日志系统"
            echo "  restart     重启日志系统"
            echo "  status      检查服务状态"
            echo "  cleanup     清理日志系统"
            echo "  logs [name] 查看服务日志"
            echo "  backup      备份Elasticsearch数据"
            echo "  info        显示系统信息"
            echo "  help        显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0 deploy          # 部署日志系统"
            echo "  $0 logs kibana     # 查看Kibana日志"
            echo "  $0 status          # 检查所有服务状态"
            echo ""
            ;;
    esac
}

# 脚本入口点
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
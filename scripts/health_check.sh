#!/bin/bash

# 象棋机器人系统 - 健康检查脚本
# 作者: 象棋机器人开发团队

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
SERVICES=(
    "chess_robot_web_gateway:8000:/health"
    "chess_robot_mongodb:27017"
    "chess_robot_redis:6379"
    "chess_robot_ai_engine"
    "chess_robot_game_manager"
)

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

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 检查容器状态
check_container_status() {
    local container_name=$1

    if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
        local status=$(docker inspect --format='{{.State.Status}}' "$container_name")
        local health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")

        if [[ "$status" == "running" ]]; then
            if [[ "$health" == "healthy" ]]; then
                echo "✅ 运行中 (健康)"
                return 0
            elif [[ "$health" == "unhealthy" ]]; then
                echo "⚠️  运行中 (不健康)"
                return 1
            else
                echo "✅ 运行中"
                return 0
            fi
        else
            echo "❌ 停止"
            return 1
        fi
    else
        echo "❌ 不存在"
        return 1
    fi
}

# 检查端口连通性
check_port_connectivity() {
    local host=${1:-localhost}
    local port=$2

    if timeout 5 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# 检查HTTP服务
check_http_service() {
    local url=$1
    local timeout=${2:-5}

    if curl -s -f --max-time "$timeout" "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 检查Redis服务
check_redis_service() {
    local container_name=$1

    if docker exec "$container_name" redis-cli ping 2>/dev/null | grep -q "PONG"; then
        return 0
    else
        return 1
    fi
}

# 检查MongoDB服务
check_mongodb_service() {
    local container_name=$1

    if docker exec "$container_name" mongosh admin --eval "db.auth('admin', 'chess_robot_2024'); db.runCommand('ping')" 2>/dev/null | grep -q "ok.*1"; then
        return 0
    else
        return 1
    fi
}

# 详细检查单个服务
detailed_service_check() {
    local service_info=$1
    IFS=':' read -r container_name port endpoint <<< "$service_info"

    echo "检查服务: $container_name"
    echo "----------------------------------------"

    # 检查容器状态
    echo -n "  容器状态: "
    if check_container_status "$container_name"; then
        container_ok=true
    else
        container_ok=false
    fi

    if [[ "$container_ok" == false ]]; then
        echo "  🔍 容器日志 (最后10行):"
        docker logs --tail 10 "$container_name" 2>/dev/null | sed 's/^/    /'
        echo ""
        return 1
    fi

    # 检查端口（如果指定）
    if [[ -n "$port" ]]; then
        echo -n "  端口连通性 ($port): "
        if check_port_connectivity "localhost" "$port"; then
            echo "✅ 可达"
        else
            echo "❌ 不可达"
        fi
    fi

    # 检查特定服务
    case $container_name in
        *web_gateway*)
            if [[ -n "$endpoint" ]]; then
                echo -n "  HTTP健康检查: "
                if check_http_service "http://localhost:$port$endpoint"; then
                    echo "✅ 正常"
                else
                    echo "❌ 异常"
                fi
            fi
            ;;
        *redis*)
            echo -n "  Redis连接: "
            if check_redis_service "$container_name"; then
                echo "✅ 正常"
            else
                echo "❌ 异常"
            fi
            ;;
        *mongodb*)
            echo -n "  MongoDB连接: "
            if check_mongodb_service "$container_name"; then
                echo "✅ 正常"
            else
                echo "❌ 异常"
            fi
            ;;
        *)
            echo "  ℹ️  基础服务 - 仅检查容器状态"
            ;;
    esac

    # 检查资源使用
    echo -n "  资源使用: "
    local stats=$(docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}" "$container_name" 2>/dev/null)
    if [[ -n "$stats" ]]; then
        echo "$stats" | tail -n 1 | awk '{print "CPU: " $1 ", 内存: " $2}'
    else
        echo "无法获取"
    fi

    echo ""
    return 0
}

# 系统整体健康检查
system_health_check() {
    echo "🏥 系统整体健康检查"
    echo "================================"

    local healthy_services=0
    local total_services=${#SERVICES[@]}

    for service_info in "${SERVICES[@]}"; do
        if detailed_service_check "$service_info"; then
            healthy_services=$((healthy_services + 1))
        fi
    done

    echo "📊 健康检查总结"
    echo "================================"
    echo "健康服务: $healthy_services/$total_services"

    local health_percentage=$((healthy_services * 100 / total_services))

    if [[ $health_percentage -eq 100 ]]; then
        log_success "🎉 所有服务运行正常！"
        return 0
    elif [[ $health_percentage -ge 80 ]]; then
        log_warn "⚠️  大部分服务正常，有少量问题"
        return 1
    elif [[ $health_percentage -ge 50 ]]; then
        log_warn "⚠️  部分服务存在问题"
        return 1
    else
        log_error "🚨 大部分服务存在严重问题"
        return 1
    fi
}

# 快速检查
quick_check() {
    echo "⚡ 快速健康检查"
    echo "================================"

    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r container_name port endpoint <<< "$service_info"
        echo -n "$container_name: "
        check_container_status "$container_name" > /dev/null
    done

    echo ""
}

# 监控模式
monitor_mode() {
    local interval=${1:-30}

    echo "📺 进入监控模式 (间隔: ${interval}秒)"
    echo "按 Ctrl+C 退出"
    echo "================================"

    while true; do
        clear
        echo "⏰ $(date '+%Y-%m-%d %H:%M:%S')"
        quick_check

        # 显示关键指标
        echo "💾 系统资源:"
        echo "  CPU使用率: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')"
        echo "  内存使用: $(free -h | awk 'NR==2{printf "%.1f%%", $3*100/$2}')"
        echo "  磁盘使用: $(df -h / | awk 'NR==2{print $5}')"

        sleep "$interval"
    done
}

# 生成健康报告
generate_report() {
    local output_file=${1:-"/tmp/chess_robot_health_report_$(date +%Y%m%d_%H%M%S).txt"}

    echo "📋 生成健康检查报告: $output_file"

    {
        echo "象棋机器人系统健康检查报告"
        echo "生成时间: $(date)"
        echo "========================================="
        echo ""

        system_health_check

        echo ""
        echo "Docker系统信息:"
        docker system df

        echo ""
        echo "运行中的容器:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Size}}"

    } > "$output_file"

    log_info "报告已生成: $output_file"
}

# 显示帮助
show_help() {
    echo "🏥 象棋机器人系统健康检查工具"
    echo "================================"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  check          执行完整健康检查 (默认)"
    echo "  quick          快速状态检查"
    echo "  monitor        监控模式"
    echo "  report         生成健康报告"
    echo "  help           显示帮助信息"
    echo ""
    echo "选项:"
    echo "  --interval N   监控模式的检查间隔 (秒，默认30)"
    echo "  --output FILE  报告输出文件路径"
    echo ""
    echo "示例:"
    echo "  $0 check                    # 完整健康检查"
    echo "  $0 quick                    # 快速检查"
    echo "  $0 monitor --interval 10    # 10秒间隔监控"
    echo "  $0 report --output /tmp/report.txt"
}

# 主函数
main() {
    local command="check"
    local interval=30
    local output_file=""

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            check|quick|monitor|report|help)
                command="$1"
                shift
                ;;
            --interval)
                interval="$2"
                shift 2
                ;;
            --output)
                output_file="$2"
                shift 2
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 执行命令
    case $command in
        check)
            system_health_check
            ;;
        quick)
            quick_check
            ;;
        monitor)
            monitor_mode "$interval"
            ;;
        report)
            if [[ -n "$output_file" ]]; then
                generate_report "$output_file"
            else
                generate_report
            fi
            ;;
        help)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@"
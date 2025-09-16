#!/bin/bash

# 智能象棋机器人认证系统管理脚本
# 用于部署和管理认证相关服务

set -e

# 配置变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AUTH_DIR="$PROJECT_ROOT/infrastructure"

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

    log_info "依赖检查完成"
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."

    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/data/mongodb"
    mkdir -p "$PROJECT_ROOT/data/redis"

    log_info "目录创建完成"
}

# 生成JWT密钥
generate_jwt_secret() {
    log_info "生成JWT密钥..."

    # 生成随机密钥
    JWT_SECRET=$(openssl rand -base64 32)

    # 创建环境变量文件
    cat > "$AUTH_DIR/.env.auth" << EOF
# 认证系统环境变量
JWT_SECRET_KEY=$JWT_SECRET
MONGODB_ROOT_PASSWORD=ChessRobotAuth2024
MONGODB_AUTH_PASSWORD=auth_pass_2024
REDIS_AUTH_PASSWORD=redis_auth_2024
DEFAULT_ADMIN_PASSWORD=ChessRobotAdmin2024!
EOF

    log_info "JWT密钥生成完成"
}

# 部署认证系统
deploy_auth() {
    log_info "部署认证和授权系统..."

    cd "$AUTH_DIR"

    # 生成密钥
    generate_jwt_secret

    # 拉取镜像
    log_info "拉取Docker镜像..."
    docker-compose -f docker-compose-auth.yml pull

    # 构建自定义镜像
    log_info "构建认证服务镜像..."
    docker-compose -f docker-compose-auth.yml build

    # 启动服务
    log_info "启动认证系统服务..."
    docker-compose -f docker-compose-auth.yml up -d

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 60

    # 检查服务状态
    check_auth_services

    log_info "认证系统部署完成"
    show_auth_info
}

# 检查认证服务状态
check_auth_services() {
    log_info "检查认证服务状态..."

    services=("mongodb_auth" "redis_auth" "auth_service" "web_gateway_auth")

    for service in "${services[@]}"; do
        if docker ps | grep -q "chess_$service"; then
            log_info "✓ $service 运行中"
        else
            log_warn "✗ $service 未运行"
        fi
    done

    # 检查认证服务健康状态
    if curl -s http://localhost:8006/health > /dev/null; then
        log_info "✓ 认证服务健康检查通过"
    else
        log_warn "✗ 认证服务健康检查失败"
    fi

    # 检查Web网关状态
    if curl -s http://localhost:8001/health > /dev/null; then
        log_info "✓ Web网关服务健康检查通过"
    else
        log_warn "✗ Web网关服务健康检查失败"
    fi
}

# 停止认证系统
stop_auth() {
    log_info "停止认证系统..."

    cd "$AUTH_DIR"
    docker-compose -f docker-compose-auth.yml stop

    log_info "认证系统已停止"
}

# 重启认证系统
restart_auth() {
    log_info "重启认证系统..."

    stop_auth
    sleep 5
    deploy_auth
}

# 清理认证系统
cleanup_auth() {
    log_info "清理认证系统..."

    cd "$AUTH_DIR"

    # 停止并删除容器
    docker-compose -f docker-compose-auth.yml down -v

    # 删除镜像（可选）
    read -p "是否删除Docker镜像? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rmi $(docker images | grep -E "chess.*auth" | awk '{print $3}') 2>/dev/null || true
    fi

    # 删除数据目录（可选）
    read -p "是否删除数据目录? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$PROJECT_ROOT/data/mongodb" "$PROJECT_ROOT/data/redis"
    fi

    log_info "认证系统清理完成"
}

# 创建管理员用户
create_admin_user() {
    log_info "创建管理员用户..."

    local username="${1:-admin}"
    local password="${2:-ChessRobotAdmin2024!}"
    local email="${3:-admin@chessrobot.local}"

    # 调用认证服务API创建用户
    curl -X POST "http://localhost:8006/api/auth/register" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"$username\",
            \"email\": \"$email\",
            \"password\": \"$password\",
            \"full_name\": \"系统管理员\"
        }" || log_error "创建管理员用户失败"

    log_info "管理员用户创建完成"
}

# 测试认证功能
test_auth() {
    log_info "测试认证功能..."

    # 测试注册
    log_info "测试用户注册..."
    register_response=$(curl -s -X POST "http://localhost:8006/api/auth/register" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123!",
            "full_name": "测试用户"
        }')

    if echo "$register_response" | grep -q "username"; then
        log_info "✓ 用户注册测试通过"
    else
        log_warn "✗ 用户注册测试失败"
        log_debug "$register_response"
    fi

    # 测试登录
    log_info "测试用户登录..."
    login_response=$(curl -s -X POST "http://localhost:8006/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "testuser",
            "password": "TestPassword123!"
        }')

    if echo "$login_response" | grep -q "access_token"; then
        log_info "✓ 用户登录测试通过"

        # 提取token进行进一步测试
        token=$(echo "$login_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

        if [ -n "$token" ]; then
            # 测试受保护的端点
            me_response=$(curl -s -H "Authorization: Bearer $token" "http://localhost:8006/api/auth/me")

            if echo "$me_response" | grep -q "testuser"; then
                log_info "✓ 令牌验证测试通过"
            else
                log_warn "✗ 令牌验证测试失败"
            fi
        fi
    else
        log_warn "✗ 用户登录测试失败"
        log_debug "$login_response"
    fi
}

# 查看认证服务日志
view_logs() {
    local service="${1:-auth_service}"

    if [ -z "$service" ]; then
        log_info "可用服务："
        docker ps --format "table {{.Names}}\t{{.Status}}" | grep chess.*auth
        return
    fi

    log_info "显示 $service 的日志..."
    docker logs -f "chess_$service"
}

# 备份认证数据
backup_auth_data() {
    log_info "备份认证数据..."

    BACKUP_DIR="$PROJECT_ROOT/backups/auth/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # 备份MongoDB
    docker exec chess_mongodb_auth mongodump --db chess_robot_auth --out /tmp/backup
    docker cp chess_mongodb_auth:/tmp/backup "$BACKUP_DIR/mongodb"

    # 备份Redis
    docker exec chess_redis_auth redis-cli --rdb /tmp/dump.rdb
    docker cp chess_redis_auth:/tmp/dump.rdb "$BACKUP_DIR/redis/"

    log_info "认证数据备份完成：$BACKUP_DIR"
}

# 显示系统信息
show_auth_info() {
    log_info "=== 智能象棋机器人认证系统信息 ==="
    echo ""
    log_info "服务端点："
    echo "  - 认证服务:      http://localhost:8006"
    echo "  - Web网关:       http://localhost:8001"
    echo "  - MongoDB:       localhost:27018"
    echo "  - Redis:         localhost:6380"
    echo ""
    log_info "默认凭据："
    echo "  - 管理员用户:    admin"
    echo "  - 管理员密码:    ChessRobotAdmin2024!"
    echo "  - MongoDB用户:   auth_user"
    echo "  - Redis密码:     redis_auth_2024"
    echo ""
    log_info "API文档："
    echo "  - 认证API:       http://localhost:8006/docs"
    echo "  - 网关API:       http://localhost:8001/docs"
    echo ""
    log_info "管理命令："
    echo "  - 查看日志:      $0 logs <service_name>"
    echo "  - 检查状态:      $0 status"
    echo "  - 测试功能:      $0 test"
    echo "  - 创建用户:      $0 create-user <username> <password> <email>"
    echo ""
}

# 主函数
main() {
    local command="${1:-help}"

    case $command in
        "deploy")
            check_dependencies
            create_directories
            deploy_auth
            ;;
        "stop")
            stop_auth
            ;;
        "restart")
            restart_auth
            ;;
        "status")
            check_auth_services
            ;;
        "cleanup")
            cleanup_auth
            ;;
        "logs")
            view_logs "$2"
            ;;
        "test")
            test_auth
            ;;
        "create-user")
            create_admin_user "$2" "$3" "$4"
            ;;
        "backup")
            backup_auth_data
            ;;
        "info")
            show_auth_info
            ;;
        "help"|*)
            echo "智能象棋机器人认证系统管理脚本"
            echo ""
            echo "用法: $0 <command> [options]"
            echo ""
            echo "命令:"
            echo "  deploy           部署认证系统"
            echo "  stop             停止认证系统"
            echo "  restart          重启认证系统"
            echo "  status           检查服务状态"
            echo "  cleanup          清理认证系统"
            echo "  logs [service]   查看服务日志"
            echo "  test             测试认证功能"
            echo "  create-user      创建管理员用户"
            echo "  backup           备份认证数据"
            echo "  info             显示系统信息"
            echo "  help             显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0 deploy                    # 部署认证系统"
            echo "  $0 logs auth_service         # 查看认证服务日志"
            echo "  $0 create-user admin pass123 admin@test.com  # 创建用户"
            echo "  $0 test                      # 测试认证功能"
            echo ""
            ;;
    esac
}

# 脚本入口点
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
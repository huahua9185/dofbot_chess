#!/bin/bash

# MongoDB和Redis数据库设置脚本
# 针对Jetson Orin Nano优化

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

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

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_warn "Docker Compose is not installed. Attempting to install..."
        install_docker_compose
    fi

    # 检查Docker服务状态
    if ! systemctl is-active --quiet docker; then
        log_info "Starting Docker service..."
        sudo systemctl start docker
        sudo systemctl enable docker
    fi

    log_info "Docker is available and running"
}

# 安装Docker Compose
install_docker_compose() {
    log_info "Installing Docker Compose..."

    # 使用pip安装docker-compose (推荐用于ARM架构)
    if command -v pip3 &> /dev/null; then
        pip3 install docker-compose
    elif command -v pip &> /dev/null; then
        pip install docker-compose
    else
        log_error "pip is not available. Please install pip first."
        exit 1
    fi

    log_info "Docker Compose installed successfully"
}

# 创建目录结构
create_directories() {
    log_info "Creating directory structure..."

    mkdir -p "$PROJECT_ROOT/infrastructure/data/mongodb/db"
    mkdir -p "$PROJECT_ROOT/infrastructure/data/mongodb/log"
    mkdir -p "$PROJECT_ROOT/infrastructure/data/redis/data"
    mkdir -p "$PROJECT_ROOT/infrastructure/data/redis/log"
    mkdir -p "$PROJECT_ROOT/infrastructure/logs/mongodb"
    mkdir -p "$PROJECT_ROOT/infrastructure/logs/redis"

    # 设置权限
    sudo chown -R $USER:$USER "$PROJECT_ROOT/infrastructure/data"
    sudo chown -R $USER:$USER "$PROJECT_ROOT/infrastructure/logs"

    # MongoDB需要特定的权限
    chmod 755 "$PROJECT_ROOT/infrastructure/data/mongodb"
    chmod 755 "$PROJECT_ROOT/infrastructure/data/mongodb/db"
    chmod 755 "$PROJECT_ROOT/infrastructure/data/mongodb/log"

    log_info "Directory structure created successfully"
}

# 创建Docker Compose文件
create_docker_compose() {
    log_info "Creating Docker Compose file for databases..."

    cat > "$PROJECT_ROOT/infrastructure/docker-compose.databases.yml" << 'EOF'
version: '3.8'

services:
  mongodb:
    image: mongo:5.0
    container_name: chess_robot_mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGODB_ROOT_USERNAME:-admin}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGODB_ROOT_PASSWORD:-chess_robot_admin}
      MONGO_INITDB_DATABASE: ${MONGODB_DATABASE:-chess_robot}
    ports:
      - "${MONGODB_PORT:-27017}:27017"
    volumes:
      - ./data/mongodb/db:/data/db
      - ./data/mongodb/log:/var/log/mongodb
      - ./configs/mongodb/mongod.conf:/etc/mongod.conf:ro
      - ./configs/mongodb/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js:ro
    command: --config /etc/mongod.conf
    networks:
      - chess_robot_network
    healthcheck:
      test: ["CMD", "mongo", "--quiet", "--eval", "db.runCommand('ping')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  redis:
    image: redis:7.0-alpine
    container_name: chess_robot_redis
    restart: unless-stopped
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - ./data/redis/data:/data
      - ./configs/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    command: redis-server /usr/local/etc/redis/redis.conf
    networks:
      - chess_robot_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  # Redis Insight (可选的Web管理界面)
  redis-insight:
    image: redislabs/redisinsight:latest
    container_name: chess_robot_redis_insight
    restart: unless-stopped
    ports:
      - "8001:8001"
    networks:
      - chess_robot_network
    depends_on:
      - redis

networks:
  chess_robot_network:
    driver: bridge
    name: chess_robot_network

volumes:
  mongodb_data:
    driver: local
  redis_data:
    driver: local
EOF

    log_info "Docker Compose file created successfully"
}

# 创建环境变量文件
create_env_file() {
    log_info "Creating environment variables file..."

    cat > "$PROJECT_ROOT/infrastructure/.env.databases" << 'EOF'
# MongoDB配置
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=chess_robot
MONGODB_ROOT_USERNAME=admin
MONGODB_ROOT_PASSWORD=chess_robot_admin

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# 日志级别
LOG_LEVEL=INFO

# 健康检查
HEALTH_CHECK_INTERVAL=30
EOF

    log_info "Environment file created successfully"
}

# 启动数据库服务
start_databases() {
    log_info "Starting database services..."

    cd "$PROJECT_ROOT/infrastructure"

    # 使用环境变量文件启动服务
    docker-compose --env-file .env.databases -f docker-compose.databases.yml up -d

    log_info "Waiting for databases to be ready..."
    sleep 10

    # 检查服务状态
    check_service_health

    log_info "Database services started successfully"
}

# 检查服务健康状态
check_service_health() {
    log_info "Checking service health..."

    # 检查MongoDB
    local mongo_retries=0
    local max_retries=12

    while [ $mongo_retries -lt $max_retries ]; do
        if docker exec chess_robot_mongodb mongo --quiet --eval "db.runCommand('ping')" > /dev/null 2>&1; then
            log_info "MongoDB is healthy"
            break
        fi

        log_debug "MongoDB not ready yet, retrying in 5 seconds... ($((mongo_retries + 1))/$max_retries)"
        sleep 5
        mongo_retries=$((mongo_retries + 1))
    done

    if [ $mongo_retries -eq $max_retries ]; then
        log_error "MongoDB failed to start properly"
        exit 1
    fi

    # 检查Redis
    local redis_retries=0

    while [ $redis_retries -lt $max_retries ]; do
        if docker exec chess_robot_redis redis-cli ping > /dev/null 2>&1; then
            log_info "Redis is healthy"
            break
        fi

        log_debug "Redis not ready yet, retrying in 5 seconds... ($((redis_retries + 1))/$max_retries)"
        sleep 5
        redis_retries=$((redis_retries + 1))
    done

    if [ $redis_retries -eq $max_retries ]; then
        log_error "Redis failed to start properly"
        exit 1
    fi
}

# 停止数据库服务
stop_databases() {
    log_info "Stopping database services..."

    cd "$PROJECT_ROOT/infrastructure"
    docker-compose -f docker-compose.databases.yml down

    log_info "Database services stopped"
}

# 重启数据库服务
restart_databases() {
    log_info "Restarting database services..."

    stop_databases
    sleep 2
    start_databases

    log_info "Database services restarted successfully"
}

# 显示服务状态
show_status() {
    log_info "Database service status:"

    cd "$PROJECT_ROOT/infrastructure"
    docker-compose -f docker-compose.databases.yml ps

    echo ""
    log_info "Database logs (last 20 lines):"
    echo "=== MongoDB logs ==="
    docker logs --tail 20 chess_robot_mongodb 2>/dev/null || echo "MongoDB container not found"

    echo ""
    echo "=== Redis logs ==="
    docker logs --tail 20 chess_robot_redis 2>/dev/null || echo "Redis container not found"
}

# 清理数据库数据
clean_data() {
    log_warn "This will DELETE ALL database data. Are you sure? (y/N)"
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Cleaning database data..."

        stop_databases

        sudo rm -rf "$PROJECT_ROOT/infrastructure/data/mongodb/db"/*
        sudo rm -rf "$PROJECT_ROOT/infrastructure/data/redis/data"/*

        log_info "Database data cleaned"
    else
        log_info "Operation cancelled"
    fi
}

# 备份数据库
backup_databases() {
    local backup_dir="$PROJECT_ROOT/infrastructure/backups/$(date +%Y%m%d_%H%M%S)"

    log_info "Creating backup directory: $backup_dir"
    mkdir -p "$backup_dir"

    # 备份MongoDB
    log_info "Backing up MongoDB..."
    docker exec chess_robot_mongodb mongodump --out /tmp/backup
    docker cp chess_robot_mongodb:/tmp/backup "$backup_dir/mongodb"

    # 备份Redis
    log_info "Backing up Redis..."
    docker exec chess_robot_redis redis-cli BGSAVE
    sleep 5  # 等待备份完成
    docker cp chess_robot_redis:/data/dump.rdb "$backup_dir/redis_dump.rdb"

    log_info "Backup completed: $backup_dir"
}

# 显示帮助信息
show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup     Setup and start database services"
    echo "  start     Start database services"
    echo "  stop      Stop database services"
    echo "  restart   Restart database services"
    echo "  status    Show service status and logs"
    echo "  clean     Clean all database data (DESTRUCTIVE)"
    echo "  backup    Backup databases"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup    # First time setup"
    echo "  $0 start    # Start services"
    echo "  $0 status   # Check status"
}

# 主函数
main() {
    case "${1:-help}" in
        setup)
            check_docker
            create_directories
            create_docker_compose
            create_env_file
            start_databases
            ;;
        start)
            start_databases
            ;;
        stop)
            stop_databases
            ;;
        restart)
            restart_databases
            ;;
        status)
            show_status
            ;;
        clean)
            clean_data
            ;;
        backup)
            backup_databases
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
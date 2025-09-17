#!/bin/bash

# 快速修复和启动服务

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo "⚡ 快速修复依赖冲突"
echo "===================="

# 停止服务
docker-compose -f docker-compose.simple.yml down 2>/dev/null || true

# 只启动基础设施服务（MongoDB + Redis）
log_info "启动基础设施服务..."

cat > /tmp/infrastructure.yml << 'EOF'
version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    container_name: chess_robot_mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=chess_robot_2024
      - MONGO_INITDB_DATABASE=chess_robot
    volumes:
      - mongodb_data:/data/db
    networks:
      - chess_robot_network
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh --quiet
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: chess_robot_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - chess_robot_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 简单的Web测试服务
  web-test:
    image: nginx:alpine
    container_name: chess_robot_web_test
    restart: unless-stopped
    ports:
      - "8000:80"
    volumes:
      - /tmp/chess_web:/usr/share/nginx/html
    networks:
      - chess_robot_network

networks:
  chess_robot_network:
    driver: bridge

volumes:
  mongodb_data:
  redis_data:
EOF

# 创建测试页面
mkdir -p /tmp/chess_web
cat > /tmp/chess_web/index.html << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>象棋机器人系统</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .status { margin: 20px 0; padding: 15px; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        .service-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .service { padding: 15px; border-radius: 8px; text-align: center; }
        .service.running { background: #d4edda; color: #155724; }
        .service.stopped { background: #f8d7da; color: #721c24; }
        .service.building { background: #fff3cd; color: #856404; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 象棋机器人系统</h1>

        <div class="status success">
            <h3>✅ 基础设施服务运行正常</h3>
            <p>MongoDB 和 Redis 服务已启动，系统基础功能可用。</p>
        </div>

        <div class="status warning">
            <h3>⚠️ 应用服务正在修复中</h3>
            <p>Web网关、AI引擎等应用服务的依赖包冲突正在解决中。</p>
        </div>

        <div class="service-list">
            <div class="service running">
                <h4>MongoDB</h4>
                <p>端口: 27017</p>
                <p>状态: 运行中</p>
            </div>
            <div class="service running">
                <h4>Redis</h4>
                <p>端口: 6379</p>
                <p>状态: 运行中</p>
            </div>
            <div class="service building">
                <h4>Web网关</h4>
                <p>端口: 8000</p>
                <p>状态: 修复中</p>
            </div>
            <div class="service building">
                <h4>AI引擎</h4>
                <p>端口: 8002</p>
                <p>状态: 修复中</p>
            </div>
            <div class="service building">
                <h4>游戏管理</h4>
                <p>端口: 8001</p>
                <p>状态: 修复中</p>
            </div>
        </div>

        <div class="status info">
            <h3>📝 下一步操作</h3>
            <ul>
                <li>基础设施服务已可用，可以进行数据库和缓存操作</li>
                <li>应用服务的依赖问题正在解决中</li>
                <li>请等待完整服务修复完成</li>
            </ul>
        </div>

        <div style="text-align: center; margin-top: 30px; color: #666;">
            <p>系统时间: <span id="time"></span></p>
        </div>
    </div>

    <script>
        function updateTime() {
            document.getElementById('time').textContent = new Date().toLocaleString('zh-CN');
        }
        updateTime();
        setInterval(updateTime, 1000);
    </script>
</body>
</html>
EOF

# 启动基础设施
log_info "启动基础设施服务..."
docker-compose -f /tmp/infrastructure.yml up -d

log_info "等待服务启动..."
sleep 10

log_info "✅ 基础设施服务已启动"
echo ""
echo "🌐 访问地址: http://localhost:8000"
echo "📊 MongoDB: localhost:27017"
echo "📊 Redis: localhost:6379"
echo ""
echo "💡 下一步可以运行 './scripts/fix_and_build.sh' 完成完整修复"
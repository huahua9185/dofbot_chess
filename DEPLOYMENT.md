# 象棋机器人系统部署指南

## 快速开始

### 一键启动（推荐）
```bash
./start.sh
```

### 手动部署
```bash
# 生产环境部署
./scripts/deploy.sh deploy

# 开发环境部署
./scripts/deploy.sh deploy-dev

# 硬件环境部署（包含摄像头和机械臂）
./scripts/deploy.sh deploy-hw
```

## 部署环境说明

### 1. 生产环境 (docker-compose.yml)
- 包含所有核心服务
- 使用优化的配置
- 适合演示和生产使用

启动的服务：
- MongoDB (数据库)
- Redis (缓存和消息队列)
- Web Gateway (API网关)
- Game Manager (游戏管理)
- AI Engine (象棋AI)
- Web UI (前端界面)

### 2. 开发环境 (docker-compose.dev.yml)
- 仅启动核心服务
- 开启调试模式
- 代码热重载
- 适合开发调试

启动的服务：
- MongoDB (开发数据库)
- Redis (开发缓存)
- Web Gateway (调试模式)
- Game Manager (调试模式)
- AI Engine (调试模式)

### 3. 硬件环境 (--profile hardware)
- 在生产环境基础上启用硬件服务
- 包含摄像头和机械臂控制
- 需要物理硬件连接

额外启动的服务：
- Vision Service (视觉识别)
- Robot Service (机器人控制)

### 4. 监控环境 (--profile monitoring)
- 可选的监控和管理工具
- Prometheus + Grafana
- Redis Insight

额外启动的服务：
- Redis Insight (Redis管理界面)
- Prometheus (监控数据收集)
- Grafana (监控仪表板)

## 常用命令

### 系统管理
```bash
# 查看系统状态
./scripts/deploy.sh status

# 启动系统
./scripts/deploy.sh start

# 停止系统
./scripts/deploy.sh stop

# 重启系统
./scripts/deploy.sh restart

# 清理系统（删除所有数据）
./scripts/deploy.sh clean --force
```

### 服务管理
```bash
# 启动特定服务
./scripts/deploy.sh start --service web-ui

# 重启特定服务
./scripts/deploy.sh restart --service ai-engine

# 查看特定服务日志
./scripts/deploy.sh logs --service mongodb
```

### 日志管理
```bash
# 查看所有服务日志
./scripts/deploy.sh logs

# 查看最近50行日志
./scripts/deploy.sh logs --lines 50

# 实时查看日志
./scripts/deploy.sh logs --service web-gateway
```

### 备份和恢复
```bash
# 备份系统数据
./scripts/deploy.sh backup

# 自定义备份名称
./scripts/deploy.sh backup my_backup_20231201
```

### 测试
```bash
# 运行所有测试
./scripts/deploy.sh test

# 运行特定服务测试
./scripts/deploy.sh test --service ai-engine
```

## 环境配置

### 环境变量文件
- `.env` - 生产环境配置
- `.env.dev` - 开发环境配置

### 主要配置项
```bash
# 数据库配置
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=chess_robot

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 服务端口
WEB_GATEWAY_PORT=8000
WEB_UI_PORT=3000

# 硬件设备
CAMERA_DEVICE=/dev/video0
SERIAL_PORT=/dev/ttyACM0
```

## 网络访问

### 默认端口
- **前端界面**: http://localhost:3000
- **API文档**: http://localhost:8000/docs
- **MongoDB**: localhost:27017
- **Redis**: localhost:6379
- **Redis Insight**: http://localhost:8001 (可选)
- **Prometheus**: http://localhost:9090 (可选)
- **Grafana**: http://localhost:3001 (可选)

## 故障排除

### 常见问题

1. **端口占用**
   ```bash
   # 检查端口占用
   sudo netstat -tlnp | grep :3000

   # 停止占用端口的服务
   sudo kill -9 <PID>
   ```

2. **权限问题**
   ```bash
   # 设置Docker权限
   sudo usermod -aG docker $USER
   newgrp docker

   # 设置设备权限
   sudo chmod 666 /dev/video0
   sudo chmod 666 /dev/ttyACM0
   ```

3. **内存不足**
   ```bash
   # 查看内存使用
   free -h

   # 清理Docker缓存
   docker system prune -f
   ```

4. **硬件设备未找到**
   ```bash
   # 检查摄像头
   ls /dev/video*

   # 检查串口设备
   ls /dev/ttyACM*
   ls /dev/ttyUSB*
   ```

### 调试模式

开发环境自动启用调试模式，可以查看详细日志：

```bash
# 查看详细错误信息
./scripts/deploy.sh logs --service web-gateway

# 进入容器调试
docker exec -it chess_robot_web_gateway_dev bash
```

### 重置系统

如果系统出现问题，可以完全重置：

```bash
# 停止所有服务
./scripts/deploy.sh stop

# 清理所有数据和镜像
./scripts/deploy.sh clean --force

# 重新部署
./scripts/deploy.sh deploy
```

## 性能优化

### Jetson Orin Nano优化
系统已针对4GB内存进行优化：

- MongoDB缓存限制为1GB
- Redis内存限制为512MB
- AI引擎使用1-2个线程
- 容器资源限制已设置

### 监控资源使用
```bash
# 查看系统资源
./scripts/deploy.sh status

# 实时监控
htop
iotop
```

## 更新系统

### 更新代码
```bash
# 拉取最新代码
git pull origin main

# 重新构建和部署
./scripts/deploy.sh deploy --force
```

### 更新依赖
```bash
# 重新构建镜像
./scripts/deploy.sh build

# 重启服务
./scripts/deploy.sh restart
```
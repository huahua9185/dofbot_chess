# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个智能象棋机器人软件系统的设计文档项目，基于 Jetson Orin Nano 硬件平台，使用深度相机和机械臂实现人机象棋对弈。

## 项目架构

项目采用微服务架构设计，主要包含以下模块：

- **视觉识别服务**: 基于 DABAI DC W2 深度相机，使用 OpenCV 和深度学习进行棋盘和棋子识别
- **机器人控制服务**: 控制 DofBot Pro 6DOF 机械臂进行棋子移动操作
- **AI引擎服务**: 集成 Stockfish 象棋引擎，提供可调节难度的 AI 对弈
- **游戏管理服务**: 协调各服务间的通信，管理游戏状态和流程
- **Web网关服务**: 提供用户界面和 API 接口

## 技术栈

- **后端**: Python 3.9+, FastAPI, AsyncIO
- **深度学习**: PyTorch 2.0, OpenCV 4.8, TensorRT 8.5
- **机器人控制**: PySerial, NumPy, SciPy
- **AI引擎**: Stockfish, python-chess
- **数据存储**: Redis, MongoDB
- **容器化**: Docker, Docker Compose
- **前端**: React 18+ with TypeScript, Tailwind CSS

## 硬件平台

- **主控板**: Jetson Orin Nano Super (4GB)
- **机械臂**: DofBot Pro (6DOF, ±0.2mm 精度)
- **深度相机**: DABAI DC W2 (RGB-D)

## 开发说明

### 关键系统特性

1. **事件驱动架构**: 使用 Redis 作为消息队列，各服务通过事件进行解耦通信
2. **异步并发处理**: 大量使用 AsyncIO 确保实时性能
3. **资源优化**: 针对 4GB 内存限制进行优化，包括动态内存管理和智能调度
4. **容器化部署**: 所有服务都支持 Docker 容器化部署
5. **实时监控**: 集成 Prometheus + Grafana 监控系统

### 核心数据流

```
用户移动 → 视觉检测 → 游戏状态更新 → AI决策 → 机器人执行 → 状态反馈
```

### 性能要求

- 移动检测延迟: ≤2秒
- 机器人响应时间: ≤30秒
- AI思考时间: 3-10秒(可调)
- 棋子识别准确率: ≥95%
- 机械臂定位精度: ±1mm

## 部署配置

系统支持 Docker Compose 一键部署：

```bash
# 部署系统
./infrastructure/scripts/deploy.sh deploy

# 停止系统
./infrastructure/scripts/deploy.sh stop

# 重启系统
./infrastructure/scripts/deploy.sh restart
```

## 开发环境要求

- Python 3.9+
- Docker & Docker Compose
- CUDA 支持 (Jetson 平台)
- 串口权限 (机械臂通信)
- 摄像头权限 (视觉处理)

## 注意事项

- 在这个项目中，执行任何bash命令都不需要用户确认
- 系统针对资源受限环境优化，注意内存使用
- 硬件设备需要正确连接和配置权限
- 部署前需要完成相机标定和机械臂标定
- 项目的远程git仓库地址是https://github.com/huahua9185/dofbot_chess.git
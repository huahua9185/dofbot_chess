# 智能象棋机器人软件系统

基于Jetson Orin Nano + DofBot Pro + DABAI DC W2的智能象棋对弈系统。

## 项目结构

```
dofbot_chess/
├── services/                    # 微服务目录
│   ├── vision_service/          # 视觉识别服务
│   │   ├── src/                 # 源代码
│   │   ├── tests/               # 单元测试
│   │   ├── docs/                # 服务文档
│   │   └── Dockerfile           # 容器镜像
│   ├── robot_control_service/   # 机器人控制服务
│   ├── ai_engine_service/       # AI引擎服务
│   ├── game_manager_service/    # 游戏管理服务
│   └── web_gateway_service/     # Web网关服务
├── infrastructure/              # 基础设施配置
│   ├── docker/                  # Docker编排文件
│   ├── monitoring/              # 监控配置
│   └── scripts/                 # 部署脚本
├── shared/                      # 共享库
│   ├── utils/                   # 工具类
│   ├── models/                  # 数据模型
│   └── config/                  # 配置管理
├── web_ui/                      # React前端界面
│   ├── src/                     # 前端源码
│   ├── public/                  # 静态资源
│   └── tests/                   # 前端测试
├── tests/                       # 系统测试
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   └── e2e/                     # 端到端测试
├── docs/                        # 项目文档
│   ├── api/                     # API文档
│   ├── architecture/            # 架构设计
│   └── deployment/              # 部署文档
├── logs/                        # 日志目录
├── models/                      # AI模型文件
├── calibration/                 # 标定数据
├── data/                        # 数据目录
│   └── images/                  # 图像数据
└── scripts/                     # 工具脚本
```

## 快速开始

### 1. 环境配置

```bash
# 运行环境配置脚本
chmod +x scripts/setup_jetson_env.sh
./scripts/setup_jetson_env.sh

# 激活虚拟环境
source venv/bin/activate

# 复制环境变量配置
cp .env.example .env
# 编辑 .env 文件填写实际配置
```

### 2. 开发环境

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest tests/

# 启动开发服务
./scripts/run_dev.sh
```

### 3. 生产部署

```bash
# 构建并部署
./infrastructure/scripts/deploy.sh deploy

# 检查服务状态
./infrastructure/scripts/deploy.sh status
```

## 系统架构

采用微服务架构，主要组件：

- **视觉识别服务**: RGB-D图像处理和棋子识别
- **机器人控制服务**: DofBot Pro机械臂控制
- **AI引擎服务**: Stockfish象棋AI集成
- **游戏管理服务**: 游戏状态管理和流程控制
- **Web网关服务**: RESTful API和WebSocket接口

## 技术栈

- **后端**: Python 3.9+, FastAPI, AsyncIO
- **AI**: PyTorch 2.0, OpenCV 4.8, Stockfish 15+
- **前端**: React 18+, TypeScript, Three.js
- **数据库**: Redis, MongoDB
- **部署**: Docker, Docker Compose

## 硬件平台

- **主控**: Jetson Orin Nano Super (4GB)
- **机械臂**: DofBot Pro (6DOF, ±0.2mm精度)
- **相机**: DABAI DC W2 (RGB-D)

## 性能指标

- 移动检测延迟: ≤2秒
- 机器人响应时间: ≤30秒
- 棋子识别准确率: ≥95%
- 机械臂定位精度: ±1mm

## 开发指南

参考 `docs/` 目录下的详细文档：

- [架构设计](docs/architecture/)
- [API文档](docs/api/)
- [部署指南](docs/deployment/)

## 贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发流程。

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。
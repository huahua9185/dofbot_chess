# Robot Control Service

DofBot Pro 6DOF机械臂控制服务，负责执行象棋移动操作。

## 功能特性

- **DofBot Pro控制**: 支持6DOF机械臂精确控制
- **逆运动学**: 实现3D坐标到关节角度转换
- **轨迹规划**: 平滑的运动路径规划
- **抓取操作**: 精确的棋子抓取和放置
- **安全控制**: 碰撞检测和紧急停止
- **事件驱动**: 基于Redis的异步消息处理

## 硬件规格

### DofBot Pro机械臂
- **自由度**: 6DOF
- **工作半径**: 280mm
- **重复定位精度**: ±0.2mm
- **负载能力**: 250g
- **关节角度范围**:
  - 基座旋转: ±135°
  - 大臂抬升: ±105°
  - 小臂抬升: ±105°
  - 腕关节1: ±105°
  - 腕关节2: ±135°
  - 腕关节3: ±180°

### 通信接口
- **接口类型**: USB转串口
- **波特率**: 115200
- **数据位**: 8位
- **校验位**: 无
- **停止位**: 1位

## 技术实现

### 控制算法
1. **逆运动学求解**: 基于几何法的6DOF逆解
2. **轨迹规划**: 关节空间线性插值
3. **运动控制**: 基于脉宽调制的舵机控制
4. **碰撞检测**: 关节限位和工作空间检查

### 坐标系统
- **世界坐标系**: 以机械臂基座为原点
- **棋盘坐标系**: 棋盘中心对齐到机械臂坐标
- **坐标转换**: 支持棋盘记谱法到物理坐标转换

### 安全机制
- **软限位**: 关节角度范围检查
- **硬限位**: 物理限位开关保护
- **紧急停止**: 立即停止所有运动
- **碰撞回避**: 路径规划时避开已知障碍

## API接口

### 控制命令
```python
# 移动命令
RobotCommand(
    command_type="move",
    from_position="e2",
    to_position="e4"
)

# 抓取命令
RobotCommand(
    command_type="pick",
    from_position="e4"
)

# 放置命令
RobotCommand(
    command_type="place",
    to_position="e5"
)

# 回原点命令
RobotCommand(command_type="home")

# 紧急停止
RobotCommand(command_type="stop")
```

### 状态反馈
```python
RobotStatus(
    is_connected=True,
    is_moving=False,
    current_position=Position6D(...),
    joint_angles=[0, 0, 0, 0, 0, 0],
    gripper_state=False,
    error_message=None
)
```

## 运行方式

### 直接运行
```bash
cd services/robot_service
python3 -m src.robot.service
```

### Docker运行
```bash
docker build -t robot-service .
docker run --device=/dev/ttyUSB0 robot-service
```

### 开发调试
```bash
# 安装依赖
pip3 install -r requirements.txt

# 运行测试
pytest tests/ -v

# 启动服务
python3 -m src.robot.service
```

## 配置参数

在 `shared/config/settings.py` 中配置：

```python
class RobotSettings:
    port: str = "/dev/ttyUSB0"           # 串口设备
    baudrate: int = 115200               # 波特率
    timeout: float = 2.0                 # 通信超时
    default_speed: int = 50              # 默认速度
    safe_height: float = 50.0            # 安全高度
    calibration_file: str = "..."        # 标定文件路径
```

## 错误处理

### 常见错误
1. **串口连接失败**: 检查设备权限和连接
2. **逆运动学无解**: 目标位置超出工作空间
3. **关节超限**: 目标角度超出安全范围
4. **通信超时**: 机械臂响应超时

### 故障恢复
1. **断线重连**: 自动重新建立串口连接
2. **状态同步**: 定期查询机械臂实际状态
3. **安全复位**: 异常时自动回到安全位置

## 性能指标

- **响应时间**: <100ms (命令接收到执行)
- **定位精度**: ±1mm (棋盘坐标系下)
- **移动速度**: 可调节 1-100%
- **抓取成功率**: >95% (标准象棋子)

## 标定说明

### 坐标系标定
1. **手动标定**: 通过示教确定关键点坐标
2. **视觉标定**: 结合相机进行自动标定
3. **精度验证**: 重复定位精度测试

### 抓取标定
1. **夹爪标定**: 不同棋子的最佳夹取力度
2. **高度标定**: 各位置的最佳抓取高度
3. **速度标定**: 不同操作的最优移动速度

## 维护说明

### 日常维护
- 检查机械臂关节润滑
- 清理夹爪接触面
- 校验定位精度

### 定期校准
- 重新执行坐标系标定
- 更新抓取参数
- 验证安全限位
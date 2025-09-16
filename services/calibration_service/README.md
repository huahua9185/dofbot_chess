# 硬件标定服务

## 概述
硬件标定服务为象棋机器人系统提供完整的相机和机械臂标定功能，确保系统能够准确地进行视觉识别和机械臂控制。

## 功能特性

### 相机标定
- **RGB相机内参标定**: 焦距、主点、畸变系数
- **深度相机标定**: DABAI DC W2深度相机参数
- **立体标定**: RGB-D相机间的外参标定
- **棋盘格检测**: 9x6棋盘格自动检测
- **去畸变处理**: 图像畸变校正

### 机械臂标定
- **零点标定**: 设置机械臂初始位置
- **DH参数优化**: 6DOF机械臂运动学参数
- **关节限位设置**: 各关节安全运动范围
- **TCP标定**: 工具中心点偏移量
- **精度验证**: 位置精度测试

### 手眼标定
- **Eye-in-Hand标定**: 相机固定在机械臂末端
- **Eye-to-Hand标定**: 相机固定在外部
- **标定算法**: Tsai、Park等多种算法
- **精度评估**: 重投影误差分析

## 系统架构

```
calibration_service/
├── camera_calibration.py    # 相机标定模块
├── robot_calibration.py     # 机械臂标定模块
├── calibration_service.py   # 标定服务API
├── requirements.txt         # Python依赖
├── Dockerfile              # Docker容器配置
└── README.md              # 本文档
```

## API接口

### 基础接口
- `GET /` - 服务状态
- `GET /status` - 标定状态查询

### 相机标定
- `POST /calibrate/camera` - 执行相机标定
- `GET /calibration/download/camera` - 下载相机标定文件

### 机器人标定
- `POST /calibrate/robot` - 执行机器人标定
- `GET /calibration/download/robot` - 下载机器人标定文件

### 手眼标定
- `POST /calibrate/hand-eye` - 执行手眼标定
- `GET /calibration/download/hand_eye` - 下载手眼标定文件

### 自动标定
- `POST /calibrate/auto` - 自动执行完整标定流程

### 验证
- `GET /verify` - 验证标定精度

## 使用指南

### 1. 相机标定

#### 准备工作
- 打印9x6棋盘格标定板（方格大小25mm）
- 确保相机连接正常
- 良好的照明条件

#### 标定步骤
```python
# 创建标定器
calibrator = CameraCalibration(board_size=(9, 6), square_size=25.0)

# 捕获标定图像（建议20-30张）
calibrator.capture_calibration_images(num_images=20)

# 执行标定
result = calibrator.calibrate_rgb_camera()

# 查看标定结果
print(f"重投影误差: {result['reprojection_error']} 像素")
print(f"相机内参:\n{result['camera_matrix']}")
```

#### 标定结果
- 相机内参矩阵 (3x3)
- 畸变系数 (5个参数)
- 重投影误差 (<1.0像素为佳)

### 2. 机械臂标定

#### 准备工作
- 机械臂通电并连接串口
- 准备测量工具（游标卡尺）
- 清空工作空间

#### 标定步骤
```python
# 创建标定器
calibrator = RobotCalibration(port='/dev/ttyACM0')

# 连接机械臂
calibrator.connect()

# 标定零点
calibrator.calibrate_home_position()

# 标定DH参数（采集30-50个位置）
calibrator.calibrate_dh_parameters(num_samples=30)

# 验证标定
calibrator.verify_calibration()
```

#### DH参数说明
| 关节 | a(mm) | d(mm) | α(rad) | θ(rad) | 限位(°) |
|------|-------|-------|--------|--------|---------|
| 1    | 0     | 105   | π/2    | θ1     | ±180    |
| 2    | 105   | 0     | 0      | θ2+π/2 | ±90     |
| 3    | 98    | 0     | 0      | θ3     | ±90     |
| 4    | 0     | 0     | π/2    | θ4     | ±90     |
| 5    | 0     | 155   | -π/2   | θ5     | ±90     |
| 6    | 0     | 0     | 0      | θ6     | ±180    |

### 3. 手眼标定

#### 准备工作
- 完成相机标定
- 完成机器人标定
- 准备棋盘格标定板

#### 标定步骤
```python
# 执行手眼标定
calibrator.calibrate_hand_eye('rgb_camera_calibration.json')

# 查看变换矩阵
print(f"手眼变换矩阵:\n{calibrator.hand_eye_matrix}")
```

#### 标定精度要求
- 位置精度: <2mm
- 姿态精度: <2°
- 采样位置: >15个

## Web界面使用

### 启动服务
```bash
python calibration_service.py
# 或使用Docker
docker run -p 8002:8002 chess-robot/calibration-service
```

### 访问界面
打开浏览器访问: http://localhost:3000/calibration

### 操作流程
1. 点击"相机标定"标签
2. 按照提示放置棋盘格
3. 采集20-30张图像
4. 点击"开始标定"
5. 查看标定结果和误差

## 标定数据存储

### 文件位置
```
/home/jetson/prog/data/calibration/
├── rgb_camera_calibration.json      # RGB相机参数
├── depth_camera_calibration.json    # 深度相机参数
├── stereo_calibration.json         # 立体标定参数
├── robot_dh_parameters.json        # 机械臂DH参数
└── hand_eye_calibration.json       # 手眼标定矩阵
```

### 数据格式
```json
{
  "camera_matrix": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
  "distortion_coefficients": [k1, k2, p1, p2, k3],
  "image_size": [width, height],
  "reprojection_error": 0.5,
  "calibration_date": "2024-01-01T12:00:00"
}
```

## 故障排除

### 相机标定问题

**问题**: 无法检测到棋盘格
- 确保棋盘格完整可见
- 调整光线避免反光
- 保持棋盘格平整
- 检查棋盘格尺寸设置

**问题**: 重投影误差过大
- 增加标定图像数量
- 确保图像覆盖整个视野
- 检查棋盘格是否变形
- 重新打印标定板

### 机械臂标定问题

**问题**: 串口连接失败
```bash
# 检查串口设备
ls /dev/ttyACM*
# 设置权限
sudo chmod 666 /dev/ttyACM0
```

**问题**: DH参数优化不收敛
- 增加采样点数量
- 确保测量精度
- 检查关节编码器
- 验证初始DH参数

### 手眼标定问题

**问题**: 标定精度不足
- 增加标定位置数量
- 确保位置分布均匀
- 避免奇异位置
- 检查相机固定是否牢固

## 性能优化

### 标定速度优化
- 使用并行处理加速图像处理
- 缓存中间计算结果
- 优化搜索算法参数

### 精度提升
- 使用亚像素角点检测
- 多次标定取平均值
- 温度补偿校正
- 使用更高精度的标定板

## 维护建议

### 定期标定
- 每月进行一次验证
- 季度进行完整标定
- 硬件更换后重新标定
- 环境变化后验证精度

### 数据备份
```bash
# 备份标定数据
cp -r /home/jetson/prog/data/calibration /backup/

# 恢复标定数据
cp -r /backup/calibration /home/jetson/prog/data/
```

## 技术规格

### 相机标定精度
- 重投影误差: <1.0像素
- 畸变校正: 径向+切向
- 标定图像: 20-30张
- 棋盘格: 9x6, 25mm

### 机械臂标定精度
- 位置精度: ±1mm
- 重复精度: ±0.5mm
- 角度精度: ±0.5°
- 采样点: 30-50个

### 手眼标定精度
- 平移精度: ±2mm
- 旋转精度: ±2°
- 标定位置: 15-20个
- 算法: Tsai/Park

## 依赖项

### Python包
- opencv-python>=4.8.0
- numpy>=1.24.0
- scipy>=1.10.0
- fastapi>=0.104.0
- pyserial>=3.5

### 系统要求
- Python 3.9+
- Ubuntu 20.04+
- USB/串口权限
- 摄像头访问权限

## 许可证
MIT License

## 支持
如有问题，请联系技术支持或查看项目Wiki。
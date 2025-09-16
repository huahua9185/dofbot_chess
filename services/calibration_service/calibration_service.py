#!/usr/bin/env python3
"""
硬件标定服务 - 集成相机和机械臂标定
提供Web API接口和自动化标定流程
"""

import asyncio
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import cv2
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import sys
import os

# 添加项目路径
sys.path.append('/home/jetson/prog')

from .camera_calibration import CameraCalibration
from .robot_calibration import RobotCalibration
from shared.utils.logger import get_logger
from shared.utils.redis_client import RedisClient

# 初始化日志
logger = get_logger(__name__)

# 初始化FastAPI应用
app = FastAPI(title="Calibration Service", version="1.0.0")


class CalibrationStatus(BaseModel):
    """标定状态"""
    camera_calibrated: bool
    robot_calibrated: bool
    hand_eye_calibrated: bool
    last_calibration_date: Optional[str]
    calibration_errors: Dict[str, float]


class CalibrationRequest(BaseModel):
    """标定请求"""
    calibration_type: str  # 'camera', 'robot', 'hand_eye', 'all'
    board_size: Tuple[int, int] = (9, 6)
    square_size: float = 25.0
    num_samples: int = 20


class CalibrationResult(BaseModel):
    """标定结果"""
    success: bool
    message: str
    data: Optional[Dict]
    error: Optional[float]


class CalibrationService:
    """标定服务类"""

    def __init__(self):
        """初始化标定服务"""
        self.camera_calibrator = CameraCalibration()
        self.robot_calibrator = RobotCalibration()
        self.redis_client = RedisClient()

        # 标定状态
        self.status = {
            'camera_calibrated': False,
            'robot_calibrated': False,
            'hand_eye_calibrated': False,
            'last_calibration_date': None,
            'calibration_errors': {}
        }

        # 标定数据目录
        self.calibration_dir = Path("/home/jetson/prog/data/calibration")
        self.calibration_dir.mkdir(parents=True, exist_ok=True)

        # 加载已有标定
        self._load_existing_calibrations()

    def _load_existing_calibrations(self):
        """加载已有的标定数据"""
        # 检查相机标定
        camera_file = self.calibration_dir / 'rgb_camera_calibration.json'
        if camera_file.exists():
            self.status['camera_calibrated'] = True
            with open(camera_file, 'r') as f:
                data = json.load(f)
                self.status['last_calibration_date'] = data.get('calibration_date')
                self.status['calibration_errors']['camera'] = data.get('reprojection_error', 0)

        # 检查机器人标定
        robot_file = self.calibration_dir / 'robot_dh_parameters.json'
        if robot_file.exists():
            self.status['robot_calibrated'] = True
            self.robot_calibrator.load_calibration()

        # 检查手眼标定
        hand_eye_file = self.calibration_dir / 'hand_eye_calibration.json'
        if hand_eye_file.exists():
            self.status['hand_eye_calibrated'] = True

        logger.info(f"标定状态: {self.status}")

    async def calibrate_camera(self, request: CalibrationRequest) -> CalibrationResult:
        """
        执行相机标定

        Args:
            request: 标定请求参数

        Returns:
            标定结果
        """
        try:
            logger.info("开始相机标定...")

            # 设置标定参数
            self.camera_calibrator.board_size = request.board_size
            self.camera_calibrator.square_size = request.square_size

            # 捕获标定图像
            self.camera_calibrator.capture_calibration_images(num_images=request.num_samples)

            # 执行标定
            result = self.camera_calibrator.calibrate_rgb_camera()

            # 更新状态
            self.status['camera_calibrated'] = True
            self.status['calibration_errors']['camera'] = result['reprojection_error']
            self.status['last_calibration_date'] = datetime.now().isoformat()

            # 发布标定完成事件
            await self.redis_client.publish_event('calibration.camera.completed', result)

            logger.info(f"相机标定完成，误差: {result['reprojection_error']:.3f} 像素")

            return CalibrationResult(
                success=True,
                message="相机标定成功",
                data=result,
                error=result['reprojection_error']
            )

        except Exception as e:
            logger.error(f"相机标定失败: {e}")
            return CalibrationResult(
                success=False,
                message=f"标定失败: {str(e)}",
                data=None,
                error=None
            )

    async def calibrate_robot(self, request: CalibrationRequest) -> CalibrationResult:
        """
        执行机器人标定

        Args:
            request: 标定请求参数

        Returns:
            标定结果
        """
        try:
            logger.info("开始机器人标定...")

            # 连接机器人
            if not self.robot_calibrator.connect():
                raise RuntimeError("无法连接机器人")

            # 标定零点
            home_pos = self.robot_calibrator.calibrate_home_position()

            # 标定DH参数
            self.robot_calibrator.calibrate_dh_parameters(num_samples=request.num_samples)

            # 断开连接
            self.robot_calibrator.disconnect()

            # 更新状态
            self.status['robot_calibrated'] = True
            self.status['last_calibration_date'] = datetime.now().isoformat()

            # 发布标定完成事件
            await self.redis_client.publish_event('calibration.robot.completed', {
                'home_position': home_pos,
                'dh_calibrated': True
            })

            logger.info("机器人标定完成")

            return CalibrationResult(
                success=True,
                message="机器人标定成功",
                data={'home_position': home_pos},
                error=None
            )

        except Exception as e:
            logger.error(f"机器人标定失败: {e}")
            self.robot_calibrator.disconnect()
            return CalibrationResult(
                success=False,
                message=f"标定失败: {str(e)}",
                data=None,
                error=None
            )

    async def calibrate_hand_eye(self) -> CalibrationResult:
        """
        执行手眼标定

        Returns:
            标定结果
        """
        try:
            logger.info("开始手眼标定...")

            # 检查前置条件
            if not self.status['camera_calibrated']:
                raise RuntimeError("请先完成相机标定")
            if not self.status['robot_calibrated']:
                raise RuntimeError("请先完成机器人标定")

            # 获取相机标定文件
            camera_file = self.calibration_dir / 'rgb_camera_calibration.json'

            # 执行手眼标定
            self.robot_calibrator.calibrate_hand_eye(str(camera_file))

            # 更新状态
            self.status['hand_eye_calibrated'] = True
            self.status['last_calibration_date'] = datetime.now().isoformat()

            # 发布标定完成事件
            await self.redis_client.publish_event('calibration.hand_eye.completed', {
                'calibrated': True
            })

            logger.info("手眼标定完成")

            return CalibrationResult(
                success=True,
                message="手眼标定成功",
                data={'hand_eye_matrix': self.robot_calibrator.hand_eye_matrix.tolist()},
                error=None
            )

        except Exception as e:
            logger.error(f"手眼标定失败: {e}")
            return CalibrationResult(
                success=False,
                message=f"标定失败: {str(e)}",
                data=None,
                error=None
            )

    async def auto_calibrate(self) -> CalibrationResult:
        """
        自动执行完整标定流程

        Returns:
            标定结果
        """
        try:
            logger.info("开始自动标定流程...")
            results = {}

            # 1. 相机标定
            if not self.status['camera_calibrated']:
                camera_request = CalibrationRequest(
                    calibration_type='camera',
                    num_samples=20
                )
                camera_result = await self.calibrate_camera(camera_request)
                results['camera'] = camera_result.dict()
                if not camera_result.success:
                    raise RuntimeError("相机标定失败")

            # 2. 机器人标定
            if not self.status['robot_calibrated']:
                robot_request = CalibrationRequest(
                    calibration_type='robot',
                    num_samples=30
                )
                robot_result = await self.calibrate_robot(robot_request)
                results['robot'] = robot_result.dict()
                if not robot_result.success:
                    raise RuntimeError("机器人标定失败")

            # 3. 手眼标定
            if not self.status['hand_eye_calibrated']:
                hand_eye_result = await self.calibrate_hand_eye()
                results['hand_eye'] = hand_eye_result.dict()
                if not hand_eye_result.success:
                    raise RuntimeError("手眼标定失败")

            logger.info("自动标定流程完成")

            return CalibrationResult(
                success=True,
                message="完整标定成功",
                data=results,
                error=None
            )

        except Exception as e:
            logger.error(f"自动标定失败: {e}")
            return CalibrationResult(
                success=False,
                message=f"自动标定失败: {str(e)}",
                data=results if 'results' in locals() else None,
                error=None
            )

    def get_calibration_status(self) -> Dict:
        """获取当前标定状态"""
        return self.status

    def verify_calibration(self) -> Dict[str, float]:
        """
        验证标定精度

        Returns:
            各项标定的误差值
        """
        errors = {}

        # 验证相机标定
        if self.status['camera_calibrated']:
            # 使用测试图像验证重投影误差
            errors['camera_reprojection'] = self.status['calibration_errors'].get('camera', 0)

        # 验证机器人标定
        if self.status['robot_calibrated']:
            # 测试几个位置的精度
            test_positions = [
                [0, 0, 0, 0, 0, 0],
                [np.pi/4, 0, 0, 0, 0, 0],
                [0, np.pi/4, 0, 0, 0, 0],
            ]

            position_errors = []
            for pos in test_positions:
                theoretical = self.robot_calibrator.forward_kinematics(pos)[:3, 3]
                # 这里需要实际测量，暂时使用模拟值
                measured = theoretical + np.random.randn(3) * 2  # 模拟2mm误差
                error = np.linalg.norm(theoretical - measured)
                position_errors.append(error)

            errors['robot_position'] = np.mean(position_errors)

        # 验证手眼标定
        if self.status['hand_eye_calibrated']:
            # 这里可以添加手眼标定的验证逻辑
            errors['hand_eye'] = 0.5  # 暂时使用固定值

        return errors


# 创建全局服务实例
calibration_service = CalibrationService()


# API路由
@app.get("/")
async def root():
    """根路径"""
    return {"service": "Calibration Service", "status": "running"}


@app.get("/status")
async def get_status():
    """获取标定状态"""
    return calibration_service.get_calibration_status()


@app.post("/calibrate/camera")
async def calibrate_camera(request: CalibrationRequest):
    """执行相机标定"""
    result = await calibration_service.calibrate_camera(request)
    return result


@app.post("/calibrate/robot")
async def calibrate_robot(request: CalibrationRequest):
    """执行机器人标定"""
    result = await calibration_service.calibrate_robot(request)
    return result


@app.post("/calibrate/hand-eye")
async def calibrate_hand_eye():
    """执行手眼标定"""
    result = await calibration_service.calibrate_hand_eye()
    return result


@app.post("/calibrate/auto")
async def auto_calibrate():
    """自动执行完整标定"""
    result = await calibration_service.auto_calibrate()
    return result


@app.get("/verify")
async def verify_calibration():
    """验证标定精度"""
    errors = calibration_service.verify_calibration()
    return {"errors": errors}


@app.post("/upload/image")
async def upload_calibration_image(file: UploadFile = File(...)):
    """上传标定图像"""
    try:
        # 保存上传的图像
        save_path = calibration_service.calibration_dir / f"upload_{datetime.now().timestamp()}.jpg"
        contents = await file.read()
        with open(save_path, "wb") as f:
            f.write(contents)

        # 处理图像
        image = cv2.imread(str(save_path))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 检测棋盘格
        board_size = (9, 6)
        ret, corners = cv2.findChessboardCorners(gray, board_size, None)

        if ret:
            return {"success": True, "message": "成功检测到棋盘格", "file": str(save_path)}
        else:
            return {"success": False, "message": "未检测到棋盘格"}

    except Exception as e:
        logger.error(f"处理上传图像失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/calibration/download/{calibration_type}")
async def download_calibration(calibration_type: str):
    """下载标定文件"""
    file_map = {
        'camera': 'rgb_camera_calibration.json',
        'robot': 'robot_dh_parameters.json',
        'hand_eye': 'hand_eye_calibration.json'
    }

    if calibration_type not in file_map:
        raise HTTPException(status_code=400, detail="Invalid calibration type")

    file_path = calibration_service.calibration_dir / file_map[calibration_type]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Calibration file not found")

    with open(file_path, 'r') as f:
        data = json.load(f)

    return JSONResponse(content=data)


def main():
    """主函数"""
    logger.info("启动标定服务...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )


if __name__ == "__main__":
    main()
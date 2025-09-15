"""
DABAI DC W2 深度相机驱动
"""
import asyncio
import cv2
import numpy as np
import time
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

from shared.utils.logger import get_logger
from shared.models.chess_models import Position3D

logger = get_logger(__name__)


class CameraStatus(Enum):
    """相机状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CAPTURING = "capturing"
    ERROR = "error"


@dataclass
class CameraIntrinsics:
    """相机内参"""
    fx: float  # x轴焦距
    fy: float  # y轴焦距
    cx: float  # 光心x坐标
    cy: float  # 光心y坐标
    k1: float = 0.0  # 径向畸变参数1
    k2: float = 0.0  # 径向畸变参数2
    p1: float = 0.0  # 切向畸变参数1
    p2: float = 0.0  # 切向畸变参数2
    k3: float = 0.0  # 径向畸变参数3

    def to_matrix(self) -> np.ndarray:
        """转换为相机矩阵"""
        return np.array([
            [self.fx, 0, self.cx],
            [0, self.fy, self.cy],
            [0, 0, 1]
        ], dtype=np.float32)

    def to_distortion(self) -> np.ndarray:
        """转换为畸变系数"""
        return np.array([self.k1, self.k2, self.p1, self.p2, self.k3], dtype=np.float32)


@dataclass
class RGBDFrame:
    """RGB-D帧数据"""
    rgb_frame: np.ndarray
    depth_frame: np.ndarray
    timestamp: float
    frame_id: int
    camera_id: str = "main"


class DABAIDC_W2_Driver:
    """DABAI DC W2深度相机驱动"""

    def __init__(self,
                 rgb_device_id: int = 0,
                 depth_device_id: int = 1,
                 config_file: Optional[str] = None):
        self.rgb_device_id = rgb_device_id
        self.depth_device_id = depth_device_id
        self.config_file = config_file

        # 相机连接
        self.rgb_cap = None
        self.depth_cap = None
        self.status = CameraStatus.DISCONNECTED

        # 相机参数（默认值）
        self.rgb_width = 1920
        self.rgb_height = 1080
        self.depth_width = 640
        self.depth_height = 480
        self.fps = 30

        # 深度处理参数
        self.depth_scale = 1000.0  # 深度值单位转换（mm）
        self.depth_min = 100       # 最小深度（mm）
        self.depth_max = 2000      # 最大深度（mm）

        # 相机内参
        self.rgb_intrinsics = None
        self.depth_intrinsics = None

        # 帧缓冲
        self.frame_buffer = asyncio.Queue(maxsize=2)
        self.capture_task = None
        self.frame_id_counter = 0

        # 性能统计
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0

        # 加载配置
        if config_file and Path(config_file).exists():
            self.load_config(config_file)

    def load_config(self, config_file: str):
        """加载相机配置"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            # 更新相机参数
            self.rgb_width = config.get('rgb_width', self.rgb_width)
            self.rgb_height = config.get('rgb_height', self.rgb_height)
            self.depth_width = config.get('depth_width', self.depth_width)
            self.depth_height = config.get('depth_height', self.depth_height)
            self.fps = config.get('fps', self.fps)

            # 加载相机内参
            if 'rgb_intrinsics' in config:
                rgb_params = config['rgb_intrinsics']
                self.rgb_intrinsics = CameraIntrinsics(**rgb_params)

            if 'depth_intrinsics' in config:
                depth_params = config['depth_intrinsics']
                self.depth_intrinsics = CameraIntrinsics(**depth_params)

            logger.info("相机配置加载成功", config_file=config_file)

        except Exception as e:
            logger.error("加载相机配置失败", error=str(e), config_file=config_file)

    async def initialize(self) -> bool:
        """初始化相机连接"""
        try:
            self.status = CameraStatus.CONNECTING
            logger.info("初始化DABAI DC W2相机",
                       rgb_id=self.rgb_device_id,
                       depth_id=self.depth_device_id)

            # 初始化RGB相机
            self.rgb_cap = cv2.VideoCapture(self.rgb_device_id)
            if not self.rgb_cap.isOpened():
                raise RuntimeError(f"无法打开RGB相机 {self.rgb_device_id}")

            # 设置RGB相机参数
            self.rgb_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.rgb_width)
            self.rgb_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.rgb_height)
            self.rgb_cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.rgb_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 减少缓冲延迟

            # 初始化深度相机
            self.depth_cap = cv2.VideoCapture(self.depth_device_id)
            if not self.depth_cap.isOpened():
                logger.warning(f"无法打开深度相机 {self.depth_device_id}，尝试其他方式")
                # 尝试使用RGB相机的深度通道（某些相机支持）
                self.depth_cap = None
            else:
                # 设置深度相机参数
                self.depth_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.depth_width)
                self.depth_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.depth_height)
                self.depth_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # 设置默认内参（如果未加载配置）
            if self.rgb_intrinsics is None:
                self._set_default_intrinsics()

            self.status = CameraStatus.CONNECTED
            logger.info("DABAI DC W2相机初始化成功",
                       rgb_size=(self.rgb_width, self.rgb_height),
                       depth_size=(self.depth_width, self.depth_height),
                       fps=self.fps)

            return True

        except Exception as e:
            self.status = CameraStatus.ERROR
            logger.error("相机初始化失败", error=str(e))
            await self.cleanup()
            return False

    def _set_default_intrinsics(self):
        """设置默认相机内参（基于典型DABAI DC W2参数）"""
        self.rgb_intrinsics = CameraIntrinsics(
            fx=1400.0, fy=1400.0,
            cx=self.rgb_width / 2, cy=self.rgb_height / 2
        )

        if self.depth_cap:
            self.depth_intrinsics = CameraIntrinsics(
                fx=580.0, fy=580.0,
                cx=self.depth_width / 2, cy=self.depth_height / 2
            )

    async def start_capture(self):
        """开始采集数据"""
        if self.status != CameraStatus.CONNECTED:
            raise RuntimeError("相机未连接")

        if self.capture_task is not None:
            logger.warning("数据采集已在运行")
            return

        self.status = CameraStatus.CAPTURING
        self.capture_task = asyncio.create_task(self._capture_loop())
        logger.info("开始数据采集")

    async def stop_capture(self):
        """停止数据采集"""
        if self.capture_task:
            self.capture_task.cancel()
            try:
                await self.capture_task
            except asyncio.CancelledError:
                pass
            self.capture_task = None

        self.status = CameraStatus.CONNECTED
        logger.info("数据采集已停止")

    async def _capture_loop(self):
        """数据采集循环"""
        logger.info("进入数据采集循环")

        try:
            while self.status == CameraStatus.CAPTURING:
                start_time = time.time()

                # 采集RGB帧
                rgb_ret, rgb_frame = self.rgb_cap.read()
                if not rgb_ret:
                    logger.error("RGB帧采集失败")
                    await asyncio.sleep(0.1)
                    continue

                # 采集深度帧
                depth_frame = None
                if self.depth_cap:
                    depth_ret, raw_depth = self.depth_cap.read()
                    if depth_ret:
                        depth_frame = self._process_depth_frame(raw_depth)
                    else:
                        logger.debug("深度帧采集失败，使用模拟深度")

                # 如果没有真实深度数据，创建模拟深度帧
                if depth_frame is None:
                    depth_frame = self._create_mock_depth_frame(rgb_frame)

                # 创建RGBD帧
                rgbd_frame = RGBDFrame(
                    rgb_frame=rgb_frame,
                    depth_frame=depth_frame,
                    timestamp=time.time(),
                    frame_id=self.frame_id_counter,
                    camera_id="dabai_dc_w2"
                )

                # 更新帧缓冲
                try:
                    self.frame_buffer.put_nowait(rgbd_frame)
                except asyncio.QueueFull:
                    # 移除最旧的帧
                    try:
                        self.frame_buffer.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self.frame_buffer.put_nowait(rgbd_frame)

                self.frame_id_counter += 1

                # 更新FPS统计
                self._update_fps_stats()

                # 控制帧率
                elapsed = time.time() - start_time
                target_interval = 1.0 / self.fps
                if elapsed < target_interval:
                    await asyncio.sleep(target_interval - elapsed)

        except asyncio.CancelledError:
            logger.info("数据采集循环被取消")
        except Exception as e:
            logger.error("数据采集循环异常", error=str(e))
            self.status = CameraStatus.ERROR

    def _process_depth_frame(self, raw_depth: np.ndarray) -> np.ndarray:
        """处理原始深度数据"""
        # 确保深度图是单通道
        if len(raw_depth.shape) == 3:
            depth_frame = cv2.cvtColor(raw_depth, cv2.COLOR_BGR2GRAY)
        else:
            depth_frame = raw_depth.copy()

        # 深度值范围限制
        depth_frame = np.clip(depth_frame, self.depth_min, self.depth_max)

        # 转换为毫米单位
        depth_frame = depth_frame.astype(np.float32) * self.depth_scale

        return depth_frame

    def _create_mock_depth_frame(self, rgb_frame: np.ndarray) -> np.ndarray:
        """创建模拟深度帧（用于没有真实深度相机的情况）"""
        # 创建基于RGB图像的简单深度估计
        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)

        # 调整大小到深度图尺寸
        depth_frame = cv2.resize(gray, (self.depth_width, self.depth_height))

        # 简单的深度映射：较亮的区域假设较近
        depth_frame = 255 - depth_frame  # 反转
        depth_frame = depth_frame.astype(np.float32)

        # 映射到实际深度范围
        depth_range = self.depth_max - self.depth_min
        depth_frame = (depth_frame / 255.0) * depth_range + self.depth_min

        return depth_frame

    def _update_fps_stats(self):
        """更新FPS统计"""
        self.fps_counter += 1
        current_time = time.time()

        if current_time - self.fps_start_time >= 1.0:
            self.current_fps = self.fps_counter / (current_time - self.fps_start_time)
            self.fps_counter = 0
            self.fps_start_time = current_time

    async def get_latest_frame(self) -> Optional[RGBDFrame]:
        """获取最新帧"""
        try:
            return self.frame_buffer.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def get_frame_blocking(self, timeout: float = 1.0) -> Optional[RGBDFrame]:
        """阻塞获取帧"""
        try:
            return await asyncio.wait_for(self.frame_buffer.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def pixel_to_3d(self, u: int, v: int, depth: float, use_rgb_intrinsics: bool = True) -> Position3D:
        """将像素坐标转换为3D坐标"""
        intrinsics = self.rgb_intrinsics if use_rgb_intrinsics else self.depth_intrinsics

        if intrinsics is None:
            raise ValueError("相机内参未设置")

        # 去除畸变（简化版）
        x_norm = (u - intrinsics.cx) / intrinsics.fx
        y_norm = (v - intrinsics.cy) / intrinsics.fy

        # 转换为3D坐标
        z = depth / 1000.0  # 转换为米
        x = x_norm * z
        y = y_norm * z

        return Position3D(x=x, y=y, z=z)

    def get_camera_info(self) -> Dict[str, Any]:
        """获取相机信息"""
        return {
            "status": self.status.value,
            "rgb_device_id": self.rgb_device_id,
            "depth_device_id": self.depth_device_id,
            "rgb_resolution": (self.rgb_width, self.rgb_height),
            "depth_resolution": (self.depth_width, self.depth_height),
            "fps": self.fps,
            "current_fps": self.current_fps,
            "frame_count": self.frame_id_counter,
            "has_depth_camera": self.depth_cap is not None,
            "rgb_intrinsics": self.rgb_intrinsics.__dict__ if self.rgb_intrinsics else None,
            "depth_intrinsics": self.depth_intrinsics.__dict__ if self.depth_intrinsics else None
        }

    async def cleanup(self):
        """清理资源"""
        logger.info("清理相机资源")

        # 停止数据采集
        await self.stop_capture()

        # 释放相机
        if self.rgb_cap:
            self.rgb_cap.release()
            self.rgb_cap = None

        if self.depth_cap:
            self.depth_cap.release()
            self.depth_cap = None

        # 清空缓冲区
        while not self.frame_buffer.empty():
            try:
                self.frame_buffer.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.status = CameraStatus.DISCONNECTED
        logger.info("相机资源清理完成")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        if await self.initialize():
            await self.start_capture()
            return self
        else:
            raise RuntimeError("相机初始化失败")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()
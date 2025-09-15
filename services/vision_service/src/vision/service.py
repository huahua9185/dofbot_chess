"""
视觉识别服务主类
"""
import asyncio
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import asdict

from shared.utils.logger import get_logger
from shared.utils.redis_client import RedisEventBus, Event
from shared.config.settings import get_settings
from shared.models.chess_models import VisionDetection

from .camera import DABAIDC_W2_Driver, CameraStatus
from .processor import VisionProcessor, DetectionMode

logger = get_logger(__name__)


class VisionService:
    """视觉识别服务"""

    def __init__(self):
        self.settings = get_settings()

        # 核心组件
        self.camera_driver = None
        self.vision_processor = None
        self.event_bus = None

        # 服务状态
        self.is_running = False
        self.processing_task = None

        # 配置参数
        self.detection_mode = DetectionMode.FULL_DETECTION
        self.processing_interval = 0.1  # 处理间隔（秒）

        # 回调函数
        self.detection_callbacks = []

        # 性能统计
        self.detection_count = 0
        self.error_count = 0
        self.last_detection_time = 0.0

    async def initialize(self) -> bool:
        """初始化服务"""
        try:
            logger.info("初始化视觉识别服务")

            # 初始化相机驱动
            self.camera_driver = DABAIDC_W2_Driver(
                rgb_device_id=self.settings.camera.rgb_device_id,
                depth_device_id=self.settings.camera.depth_device_id,
                config_file=self.settings.camera.calibration_file
            )

            if not await self.camera_driver.initialize():
                logger.error("相机驱动初始化失败")
                return False

            # 初始化视觉处理器
            self.vision_processor = VisionProcessor()

            # 初始化事件总线
            self.event_bus = RedisEventBus(self.settings.redis.url)
            await self.event_bus.connect()

            # 注册事件处理
            self.event_bus.subscribe("vision_mode_change", self._handle_mode_change)
            self.event_bus.subscribe("vision_calibrate", self._handle_calibration_request)

            logger.info("视觉识别服务初始化成功")
            return True

        except Exception as e:
            logger.error("视觉识别服务初始化失败", error=str(e))
            await self.cleanup()
            return False

    async def start(self):
        """启动服务"""
        if self.is_running:
            logger.warning("服务已在运行")
            return

        try:
            logger.info("启动视觉识别服务")

            # 启动相机采集
            await self.camera_driver.start_capture()

            # 启动事件监听
            asyncio.create_task(self.event_bus.start_listening())

            # 启动视觉处理循环
            self.is_running = True
            self.processing_task = asyncio.create_task(self._processing_loop())

            logger.info("视觉识别服务启动成功")

        except Exception as e:
            logger.error("视觉识别服务启动失败", error=str(e))
            await self.stop()

    async def stop(self):
        """停止服务"""
        if not self.is_running:
            return

        logger.info("停止视觉识别服务")

        self.is_running = False

        # 停止处理循环
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
            self.processing_task = None

        # 停止事件监听
        if self.event_bus:
            await self.event_bus.stop_listening()

        logger.info("视觉识别服务已停止")

    async def cleanup(self):
        """清理资源"""
        logger.info("清理视觉识别服务资源")

        await self.stop()

        # 清理相机
        if self.camera_driver:
            await self.camera_driver.cleanup()
            self.camera_driver = None

        # 清理事件总线
        if self.event_bus:
            await self.event_bus.disconnect()
            self.event_bus = None

        self.vision_processor = None
        self.detection_callbacks.clear()

        logger.info("视觉识别服务资源清理完成")

    async def _processing_loop(self):
        """视觉处理主循环"""
        logger.info("开始视觉处理循环")

        try:
            while self.is_running:
                await self._process_single_frame()
                await asyncio.sleep(self.processing_interval)

        except asyncio.CancelledError:
            logger.info("视觉处理循环被取消")
        except Exception as e:
            logger.error("视觉处理循环异常", error=str(e))
            self.error_count += 1

    async def _process_single_frame(self):
        """处理单帧图像"""
        try:
            # 获取最新帧
            frame = await self.camera_driver.get_latest_frame()
            if frame is None:
                return

            # 视觉处理
            detection = await self.vision_processor.process_frame(
                frame, self.detection_mode
            )

            # 更新统计
            self.detection_count += 1
            self.last_detection_time = time.time()

            # 发布检测结果事件
            if detection.detection_confidence > 0.5:  # 置信度阈值
                await self._publish_detection_event(detection)

            # 调用回调函数
            for callback in self.detection_callbacks:
                try:
                    await callback(detection)
                except Exception as e:
                    logger.error("检测回调异常", error=str(e))

        except Exception as e:
            logger.error("单帧处理异常", error=str(e))
            self.error_count += 1

    async def _publish_detection_event(self, detection: VisionDetection):
        """发布检测结果事件"""
        try:
            if detection.detected_move:
                # 发布移动检测事件
                event = Event(
                    event_type="move_detected",
                    payload={
                        "move": {
                            "from_square": detection.detected_move.from_square,
                            "to_square": detection.detected_move.to_square,
                            "piece": detection.detected_move.piece.value,
                            "notation": detection.detected_move.notation
                        },
                        "confidence": detection.detection_confidence,
                        "timestamp": detection.image_timestamp,
                        "camera_id": detection.camera_id
                    },
                    source="vision_service",
                    timestamp=time.time()
                )
                await self.event_bus.publish(event)
                logger.info("发布移动检测事件",
                           move=f"{detection.detected_move.from_square}-{detection.detected_move.to_square}")

            if detection.board_state:
                # 发布棋盘状态事件
                event = Event(
                    event_type="board_state_detected",
                    payload={
                        "board_state": {
                            "pieces": {pos: asdict(piece) for pos, piece in detection.board_state.pieces.items()},
                            "timestamp": detection.board_state.timestamp,
                            "fen_string": detection.board_state.fen_string,
                            "move_count": detection.board_state.move_count
                        },
                        "confidence": detection.detection_confidence,
                        "processing_time": detection.processing_time
                    },
                    source="vision_service",
                    timestamp=time.time()
                )
                await self.event_bus.publish(event)
                logger.debug("发布棋盘状态事件", pieces_count=len(detection.board_state.pieces))

        except Exception as e:
            logger.error("发布检测事件失败", error=str(e))

    async def _handle_mode_change(self, event: Event):
        """处理检测模式变更事件"""
        try:
            mode_name = event.payload.get("mode")
            if mode_name:
                self.detection_mode = DetectionMode(mode_name)
                logger.info("检测模式已变更", mode=mode_name)
        except Exception as e:
            logger.error("处理模式变更事件失败", error=str(e))

    async def _handle_calibration_request(self, event: Event):
        """处理标定请求事件"""
        try:
            logger.info("收到相机标定请求")
            # 这里可以实现相机标定逻辑
            # 目前返回成功响应
            response_event = Event(
                event_type="vision_calibration_result",
                payload={
                    "success": True,
                    "message": "标定功能尚未实现"
                },
                source="vision_service",
                timestamp=time.time()
            )
            await self.event_bus.publish(response_event)
        except Exception as e:
            logger.error("处理标定请求失败", error=str(e))

    def add_detection_callback(self, callback: Callable[[VisionDetection], None]):
        """添加检测回调函数"""
        self.detection_callbacks.append(callback)

    def remove_detection_callback(self, callback: Callable[[VisionDetection], None]):
        """移除检测回调函数"""
        if callback in self.detection_callbacks:
            self.detection_callbacks.remove(callback)

    async def capture_single_frame(self) -> Optional[VisionDetection]:
        """手动捕获单帧进行检测"""
        try:
            frame = await self.camera_driver.get_frame_blocking(timeout=2.0)
            if frame is None:
                return None

            return await self.vision_processor.process_frame(frame, self.detection_mode)

        except Exception as e:
            logger.error("单帧捕获失败", error=str(e))
            return None

    def set_detection_mode(self, mode: DetectionMode):
        """设置检测模式"""
        self.detection_mode = mode
        logger.info("检测模式已设置", mode=mode.value)

    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        camera_info = {}
        processor_stats = {}

        if self.camera_driver:
            camera_info = self.camera_driver.get_camera_info()

        if self.vision_processor:
            processor_stats = self.vision_processor.get_performance_stats()

        return {
            "is_running": self.is_running,
            "detection_mode": self.detection_mode.value,
            "detection_count": self.detection_count,
            "error_count": self.error_count,
            "last_detection_time": self.last_detection_time,
            "camera_info": camera_info,
            "processor_stats": processor_stats,
            "processing_interval": self.processing_interval
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        if await self.initialize():
            await self.start()
            return self
        else:
            raise RuntimeError("视觉服务初始化失败")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()
"""
视觉服务测试程序
"""
import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.utils.logger import setup_logging
from vision.camera import DABAIDC_W2_Driver, CameraStatus
from vision.processor import VisionProcessor, DetectionMode
from vision.service import VisionService

logger = setup_logging("vision_test", log_dir="/home/jetson/prog/logs")


async def test_camera_driver():
    """测试相机驱动"""
    logger.info("开始测试相机驱动")

    try:
        # 创建相机驱动实例
        camera = DABAIDC_W2_Driver(rgb_device_id=0, depth_device_id=1)

        # 测试初始化
        if not await camera.initialize():
            logger.warning("相机初始化失败，可能是因为没有连接实际硬件")
            return False

        logger.info("相机初始化成功", info=camera.get_camera_info())

        # 测试数据采集
        await camera.start_capture()
        logger.info("开始数据采集")

        # 采集几帧数据
        for i in range(5):
            frame = await camera.get_frame_blocking(timeout=2.0)
            if frame:
                logger.info(f"采集到第{i+1}帧",
                           frame_id=frame.frame_id,
                           rgb_shape=frame.rgb_frame.shape,
                           depth_shape=frame.depth_frame.shape if frame.depth_frame is not None else None)
            else:
                logger.warning(f"第{i+1}帧采集超时")

            await asyncio.sleep(0.5)

        # 清理资源
        await camera.cleanup()
        logger.info("相机驱动测试完成")
        return True

    except Exception as e:
        logger.error("相机驱动测试异常", error=str(e))
        return False


async def test_vision_processor():
    """测试视觉处理器"""
    logger.info("开始测试视觉处理器")

    try:
        # 创建处理器
        processor = VisionProcessor()

        # 创建模拟帧数据
        import numpy as np
        rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        depth_frame = np.full((480, 640), 500.0, dtype=np.float32)

        from vision.camera import RGBDFrame
        mock_frame = RGBDFrame(
            rgb_frame=rgb_frame,
            depth_frame=depth_frame,
            timestamp=time.time(),
            frame_id=1,
            camera_id="test"
        )

        # 测试不同检测模式
        for mode in DetectionMode:
            logger.info(f"测试检测模式: {mode.value}")
            detection = await processor.process_frame(mock_frame, mode)

            logger.info("检测结果",
                       confidence=detection.detection_confidence,
                       processing_time=detection.processing_time,
                       has_board_state=detection.board_state is not None,
                       has_move=detection.detected_move is not None)

        # 性能统计
        stats = processor.get_performance_stats()
        logger.info("处理器性能统计", stats=stats)

        logger.info("视觉处理器测试完成")
        return True

    except Exception as e:
        logger.error("视觉处理器测试异常", error=str(e))
        return False


async def test_vision_service():
    """测试完整视觉服务"""
    logger.info("开始测试视觉服务")

    try:
        # 创建视觉服务
        service = VisionService()

        # 添加检测回调
        detection_results = []

        async def detection_callback(detection):
            detection_results.append(detection)
            logger.info("收到检测回调",
                       confidence=detection.detection_confidence,
                       timestamp=detection.image_timestamp)

        service.add_detection_callback(detection_callback)

        # 初始化服务
        if not await service.initialize():
            logger.warning("视觉服务初始化失败，可能是因为Redis未运行或相机未连接")
            return False

        logger.info("视觉服务初始化成功")

        # 启动服务
        await service.start()
        logger.info("视觉服务启动成功")

        # 获取服务状态
        status = service.get_service_status()
        logger.info("服务状态", status=status)

        # 运行一段时间
        await asyncio.sleep(5.0)

        # 尝试手动捕获一帧
        detection = await service.capture_single_frame()
        if detection:
            logger.info("手动捕获成功",
                       confidence=detection.detection_confidence,
                       processing_time=detection.processing_time)

        # 检查回调结果
        logger.info(f"收到了 {len(detection_results)} 个检测结果")

        # 清理服务
        await service.cleanup()
        logger.info("视觉服务测试完成")
        return True

    except Exception as e:
        logger.error("视觉服务测试异常", error=str(e))
        return False


async def main():
    """主测试函数"""
    logger.info("开始视觉服务测试套件")

    tests = [
        ("相机驱动测试", test_camera_driver),
        ("视觉处理器测试", test_vision_processor),
        ("视觉服务测试", test_vision_service)
    ]

    results = []

    for test_name, test_func in tests:
        logger.info(f"运行测试: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
            logger.info(f"测试 {test_name} {'通过' if result else '失败'}")
        except Exception as e:
            logger.error(f"测试 {test_name} 异常", error=str(e))
            results.append((test_name, False))

        # 测试间隔
        await asyncio.sleep(1.0)

    # 汇总结果
    logger.info("测试结果汇总:")
    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"  {test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"测试完成: {passed}/{total} 通过")

    if passed == total:
        logger.info("🎉 所有测试通过!")
        return 0
    else:
        logger.warning("⚠️ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
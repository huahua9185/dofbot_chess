"""
视觉识别服务主程序
"""
import asyncio
import signal
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.utils.logger import setup_logging
from shared.config.settings import get_settings
from vision.service import VisionService

# 设置日志
logger = setup_logging("vision_service")


class VisionServiceManager:
    """视觉服务管理器"""

    def __init__(self):
        self.vision_service = None
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """启动服务"""
        try:
            logger.info("启动视觉识别服务管理器")

            # 创建视觉服务实例
            self.vision_service = VisionService()

            # 初始化并启动
            if not await self.vision_service.initialize():
                logger.error("视觉服务初始化失败")
                return False

            await self.vision_service.start()

            logger.info("视觉识别服务启动成功，等待信号...")

            # 等待关闭信号
            await self.shutdown_event.wait()

            return True

        except Exception as e:
            logger.error("启动视觉服务失败", error=str(e))
            return False

    async def stop(self):
        """停止服务"""
        logger.info("正在关闭视觉识别服务...")

        if self.vision_service:
            await self.vision_service.cleanup()

        self.shutdown_event.set()
        logger.info("视觉识别服务已关闭")

    def handle_shutdown_signal(self, signum, frame):
        """处理关闭信号"""
        logger.info(f"收到关闭信号 {signum}")
        asyncio.create_task(self.stop())


async def main():
    """主函数"""
    # 获取配置
    settings = get_settings()
    logger.info("启动视觉识别服务",
                service_name=settings.service_name,
                environment=settings.environment)

    # 创建服务管理器
    manager = VisionServiceManager()

    # 注册信号处理器
    signal.signal(signal.SIGINT, manager.handle_shutdown_signal)
    signal.signal(signal.SIGTERM, manager.handle_shutdown_signal)

    try:
        # 启动服务
        success = await manager.start()

        if success:
            logger.info("视觉识别服务运行完成")
        else:
            logger.error("视觉识别服务启动失败")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
        await manager.stop()
    except Exception as e:
        logger.error("服务运行异常", error=str(e))
        await manager.stop()
        sys.exit(1)


if __name__ == "__main__":
    # 设置事件循环策略（Linux上避免线程问题）
    if sys.platform.startswith('linux'):
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    # 运行主函数
    asyncio.run(main())
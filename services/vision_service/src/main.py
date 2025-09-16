"""
视觉识别服务主程序
"""
import asyncio
import signal
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.logging import setup_logging, get_logger, log_async_function_call, LogContext
from shared.config.settings import get_settings
from vision.service import VisionService

# 设置结构化日志
logger = setup_logging("vision_service")


class VisionServiceManager:
    """视觉服务管理器"""

    def __init__(self):
        self.vision_service = None
        self.shutdown_event = asyncio.Event()

    @log_async_function_call(log_duration=True)
    async def start(self):
        """启动服务"""
        with LogContext(service_name="vision_service", operation="service_start"):
            try:
                logger.info("启动视觉识别服务管理器", extra={
                    'event': 'service_starting',
                    'service_type': 'vision',
                    'component': 'manager'
                })

                # 创建视觉服务实例
                self.vision_service = VisionService()

                # 初始化并启动
                if not await self.vision_service.initialize():
                    logger.error("视觉服务初始化失败", extra={
                        'event': 'service_initialization_failed',
                        'reason': 'vision_service_initialize_returned_false'
                    })
                    return False

                await self.vision_service.start()

                logger.info("视觉识别服务启动成功，等待信号...", extra={
                    'event': 'service_started',
                    'status': 'ready',
                    'waiting_for': 'shutdown_signal'
                })

                # 等待关闭信号
                await self.shutdown_event.wait()

                return True

            except Exception as e:
                logger.error("启动视觉服务失败", extra={
                    'event': 'service_start_failed',
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }, exc_info=True)
                return False

    @log_async_function_call(log_duration=True)
    async def stop(self):
        """停止服务"""
        with LogContext(service_name="vision_service", operation="service_stop"):
            logger.info("正在关闭视觉识别服务...", extra={
                'event': 'service_stopping',
                'service_type': 'vision'
            })

            if self.vision_service:
                try:
                    await self.vision_service.cleanup()
                    logger.info("视觉服务清理完成", extra={
                        'event': 'service_cleanup_completed'
                    })
                except Exception as e:
                    logger.error("视觉服务清理失败", extra={
                        'event': 'service_cleanup_failed',
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    }, exc_info=True)

            self.shutdown_event.set()
            logger.info("视觉识别服务已关闭", extra={
                'event': 'service_stopped',
                'status': 'shutdown'
            })

    def handle_shutdown_signal(self, signum, frame):
        """处理关闭信号"""
        logger.info(f"收到关闭信号 {signum}")
        asyncio.create_task(self.stop())


@log_async_function_call(log_duration=True)
async def main():
    """主函数"""
    with LogContext(service_name="vision_service", operation="main_execution"):
        # 获取配置
        settings = get_settings()
        logger.info("启动视觉识别服务", extra={
            'event': 'service_main_starting',
            'service_name': settings.service_name,
            'environment': settings.environment,
            'pid': sys.argv[0] if sys.argv else 'unknown',
            'python_version': sys.version
        })

        # 创建服务管理器
        manager = VisionServiceManager()

        # 注册信号处理器
        signal.signal(signal.SIGINT, manager.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, manager.handle_shutdown_signal)
        logger.info("信号处理器注册完成", extra={
            'event': 'signal_handlers_registered',
            'signals': ['SIGINT', 'SIGTERM']
        })

        try:
            # 启动服务
            success = await manager.start()

            if success:
                logger.info("视觉识别服务运行完成", extra={
                    'event': 'service_main_completed',
                    'status': 'success'
                })
            else:
                logger.error("视觉识别服务启动失败", extra={
                    'event': 'service_main_failed',
                    'status': 'startup_failed'
                })
                sys.exit(1)

        except KeyboardInterrupt:
            logger.info("收到键盘中断信号", extra={
                'event': 'keyboard_interrupt',
                'signal_type': 'SIGINT'
            })
            await manager.stop()
        except Exception as e:
            logger.error("服务运行异常", extra={
                'event': 'service_main_exception',
                'error_type': type(e).__name__,
                'error_message': str(e)
            }, exc_info=True)
            await manager.stop()
            sys.exit(1)


if __name__ == "__main__":
    # 设置事件循环策略（Linux上避免线程问题）
    if sys.platform.startswith('linux'):
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    # 运行主函数
    asyncio.run(main())
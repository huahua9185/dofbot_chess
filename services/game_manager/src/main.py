"""
游戏管理服务主入口
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.event_bus import EventBus
from shared.config import get_config
from shared.logging_config import setup_logging
from .game_manager import GameManager


logger = logging.getLogger(__name__)


class GameManagerService:
    """游戏管理服务"""

    def __init__(self):
        """初始化服务"""
        self.config = get_config()
        self.event_bus = None
        self.game_manager = None
        self.running = False

    async def start(self):
        """启动服务"""
        try:
            # 设置日志
            setup_logging(self.config.logging)

            logger.info("Starting Game Manager Service...")

            # 初始化事件总线
            self.event_bus = EventBus(self.config.redis)
            await self.event_bus.connect()

            # 初始化游戏管理器
            self.game_manager = GameManager(self.event_bus)
            await self.game_manager.start()

            self.running = True

            # 发布服务启动事件
            from shared.models import Event
            await self.event_bus.publish("service.game_manager.status", Event(
                type="service.status",
                payload={
                    "service": "game_manager",
                    "status": "running",
                    "timestamp": asyncio.get_event_loop().time()
                }
            ))

            logger.info("Game Manager Service started successfully")

            # 保持服务运行
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error starting Game Manager Service: {e}")
            raise

    async def stop(self):
        """停止服务"""
        logger.info("Stopping Game Manager Service...")
        self.running = False

        if self.game_manager:
            await self.game_manager.stop()

        if self.event_bus:
            # 发布服务停止事件
            from shared.models import Event
            await self.event_bus.publish("service.game_manager.status", Event(
                type="service.status",
                payload={
                    "service": "game_manager",
                    "status": "stopped",
                    "timestamp": asyncio.get_event_loop().time()
                }
            ))
            await self.event_bus.close()

        logger.info("Game Manager Service stopped")

    async def health_check(self):
        """健康检查"""
        if not self.running or not self.game_manager:
            return False

        # 检查事件总线连接
        if not self.event_bus or not self.event_bus.is_connected():
            return False

        return True


# 全局服务实例
service = GameManagerService()


def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"Received signal {signum}, shutting down...")
    asyncio.create_task(service.stop())


async def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        logger.error(f"Service error: {e}")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
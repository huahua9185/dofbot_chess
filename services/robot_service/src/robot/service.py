"""
机器人控制服务主程序
"""
import asyncio
import json
from typing import Optional, Dict, Any
from dataclasses import asdict
import logging

from shared.models.chess_models import RobotCommand, RobotStatus, GameState
from shared.utils.redis_client import RedisEventBus, Event
from shared.utils.logger import get_logger
from shared.config.settings import get_settings
from .controller import DofBotProController

settings = get_settings()
logger = get_logger(__name__)


class RobotService:
    """机器人控制服务"""

    def __init__(self):
        self.service_name = "robot_service"
        self.controller = DofBotProController()
        self.event_bus: Optional[RedisEventBus] = None
        self.is_running = False
        self.current_command: Optional[RobotCommand] = None
        self.command_queue = asyncio.Queue()

    async def initialize(self) -> bool:
        """初始化服务"""
        try:
            logger.info(f"初始化{self.service_name}")

            # 连接Redis事件总线
            self.event_bus = RedisEventBus()
            if not await self.event_bus.connect():
                logger.error("连接Redis失败")
                return False

            # 初始化机械臂
            if not await self.controller.initialize():
                logger.error("初始化机械臂失败")
                return False

            # 订阅事件
            await self._setup_event_subscriptions()

            logger.info("机器人服务初始化完成")
            return True

        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            return False

    async def _setup_event_subscriptions(self):
        """设置事件订阅"""
        await self.event_bus.subscribe("chess_robot:robot_command", self._handle_robot_command)
        await self.event_bus.subscribe("chess_robot:game_state_changed", self._handle_game_state_change)
        await self.event_bus.subscribe("chess_robot:emergency_stop", self._handle_emergency_stop)
        logger.info("事件订阅设置完成")

    async def _handle_robot_command(self, event_data: Dict[str, Any]):
        """处理机器人控制命令"""
        try:
            logger.info(f"收到机器人命令: {event_data}")

            # 解析命令
            command_data = event_data.get("data", {})
            command = RobotCommand(
                command_type=command_data.get("command_type"),
                from_position=command_data.get("from_position"),
                to_position=command_data.get("to_position"),
                speed=command_data.get("speed", settings.robot.default_speed),
                precision=command_data.get("precision", 1.0),
                timeout=command_data.get("timeout", 30.0)
            )

            # 加入命令队列
            await self.command_queue.put(command)

        except Exception as e:
            logger.error(f"处理机器人命令失败: {str(e)}")

    async def _handle_game_state_change(self, event_data: Dict[str, Any]):
        """处理游戏状态变化"""
        try:
            logger.info(f"游戏状态变化: {event_data}")

            game_data = event_data.get("data", {})
            status = game_data.get("status")

            if status == "finished":
                # 游戏结束，回到原点
                await self.command_queue.put(
                    RobotCommand(command_type="home")
                )

        except Exception as e:
            logger.error(f"处理游戏状态变化失败: {str(e)}")

    async def _handle_emergency_stop(self, event_data: Dict[str, Any]):
        """处理紧急停止"""
        try:
            logger.warning("收到紧急停止信号")
            await self.controller.emergency_stop()

            # 清空命令队列
            while not self.command_queue.empty():
                try:
                    self.command_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            # 发送状态更新
            await self._publish_status()

        except Exception as e:
            logger.error(f"处理紧急停止失败: {str(e)}")

    async def _execute_command(self, command: RobotCommand) -> bool:
        """执行机器人命令"""
        self.current_command = command
        success = False

        try:
            logger.info(f"执行命令: {command.command_type}")

            if command.command_type == "move":
                # 执行移动
                if command.from_position and command.to_position:
                    success = await self.controller.execute_move(
                        command.from_position,
                        command.to_position
                    )
                else:
                    logger.error("移动命令缺少位置参数")

            elif command.command_type == "pick":
                # 抓取操作
                if command.from_position:
                    success = await self.controller.pick_piece(command.from_position)
                else:
                    logger.error("抓取命令缺少位置参数")

            elif command.command_type == "place":
                # 放置操作
                if command.to_position:
                    success = await self.controller.place_piece(command.to_position)
                else:
                    logger.error("放置命令缺少位置参数")

            elif command.command_type == "home":
                # 回到原点
                success = await self.controller.home()

            elif command.command_type == "stop":
                # 停止运动
                await self.controller.emergency_stop()
                success = True

            else:
                logger.error(f"未知命令类型: {command.command_type}")

            # 发布命令执行结果
            await self._publish_command_result(command, success)

        except Exception as e:
            logger.error(f"执行命令失败: {str(e)}")
            await self._publish_command_result(command, False, str(e))

        finally:
            self.current_command = None

        return success

    async def _publish_command_result(self, command: RobotCommand, success: bool, error: str = ""):
        """发布命令执行结果"""
        try:
            event = Event(
                event_type="robot_command_result",
                payload={
                    "command": asdict(command),
                    "success": success,
                    "error": error,
                    "timestamp": asyncio.get_event_loop().time()
                },
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布命令结果失败: {str(e)}")

    async def _publish_status(self):
        """发布机器人状态"""
        try:
            status = self.controller.get_status()

            event = Event(
                event_type="robot_status_update",
                payload=asdict(status),
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布状态失败: {str(e)}")

    async def _command_processor(self):
        """命令处理协程"""
        while self.is_running:
            try:
                # 等待命令
                command = await asyncio.wait_for(
                    self.command_queue.get(),
                    timeout=1.0
                )

                # 执行命令
                await self._execute_command(command)

                # 更新状态
                await self._publish_status()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"命令处理器错误: {str(e)}")

    async def _status_reporter(self):
        """状态报告协程"""
        while self.is_running:
            try:
                await self._publish_status()
                await asyncio.sleep(5.0)  # 每5秒发送一次状态
            except Exception as e:
                logger.error(f"状态报告器错误: {str(e)}")

    async def run(self):
        """运行服务"""
        self.is_running = True
        logger.info("机器人服务开始运行")

        try:
            # 启动所有协程
            tasks = [
                asyncio.create_task(self._command_processor()),
                asyncio.create_task(self._status_reporter()),
                asyncio.create_task(self.event_bus.start_listening())
            ]

            # 等待任务完成
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            logger.info("收到停止信号")
        except Exception as e:
            logger.error(f"服务运行错误: {str(e)}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """关闭服务"""
        logger.info("正在关闭机器人服务")
        self.is_running = False

        try:
            # 断开机械臂连接
            await self.controller.disconnect()

            # 断开Redis连接
            if self.event_bus:
                await self.event_bus.disconnect()

            logger.info("机器人服务已关闭")

        except Exception as e:
            logger.error(f"关闭服务时出错: {str(e)}")


async def main():
    """主函数"""
    service = RobotService()

    if not await service.initialize():
        logger.error("服务初始化失败")
        return

    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
"""
机器人服务测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from shared.models.chess_models import RobotCommand, RobotStatus
from services.robot_service.src.robot.service import RobotService


class TestRobotService:
    """机器人服务测试类"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return RobotService()

    @pytest.fixture
    def mock_controller(self):
        """模拟控制器"""
        controller = Mock()
        controller.initialize = AsyncMock(return_value=True)
        controller.disconnect = AsyncMock()
        controller.execute_move = AsyncMock(return_value=True)
        controller.pick_piece = AsyncMock(return_value=True)
        controller.place_piece = AsyncMock(return_value=True)
        controller.home = AsyncMock(return_value=True)
        controller.emergency_stop = AsyncMock()
        controller.get_status = Mock(return_value=RobotStatus(
            is_connected=True,
            is_moving=False,
            current_position=Mock(),
            joint_angles=[0] * 6,
            gripper_state=False
        ))
        return controller

    @pytest.fixture
    def mock_event_bus(self):
        """模拟事件总线"""
        event_bus = Mock()
        event_bus.connect = AsyncMock(return_value=True)
        event_bus.disconnect = AsyncMock()
        event_bus.subscribe = AsyncMock()
        event_bus.publish = AsyncMock()
        event_bus.start_listening = AsyncMock()
        return event_bus

    def test_init(self, service):
        """测试初始化"""
        assert service.service_name == "robot_service"
        assert service.controller is not None
        assert not service.is_running
        assert service.current_command is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, service, mock_controller, mock_event_bus):
        """测试服务初始化成功"""
        service.controller = mock_controller

        with patch('services.robot_service.src.robot.service.RedisEventBus', return_value=mock_event_bus):
            success = await service.initialize()

            assert success
            mock_event_bus.connect.assert_called_once()
            mock_controller.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_redis_failure(self, service, mock_controller):
        """测试Redis连接失败"""
        service.controller = mock_controller

        with patch('services.robot_service.src.robot.service.RedisEventBus') as mock_bus_class:
            mock_bus = mock_bus_class.return_value
            mock_bus.connect = AsyncMock(return_value=False)

            success = await service.initialize()

            assert not success

    @pytest.mark.asyncio
    async def test_initialize_controller_failure(self, service, mock_event_bus):
        """测试控制器初始化失败"""
        with patch('services.robot_service.src.robot.service.RedisEventBus', return_value=mock_event_bus), \
             patch.object(service.controller, 'initialize', return_value=False):

            success = await service.initialize()

            assert not success

    @pytest.mark.asyncio
    async def test_handle_robot_command(self, service):
        """测试处理机器人命令"""
        event_data = {
            "data": {
                "command_type": "move",
                "from_position": "e2",
                "to_position": "e4",
                "speed": 50
            }
        }

        await service._handle_robot_command(event_data)

        # 检查命令是否加入队列
        assert not service.command_queue.empty()
        command = await service.command_queue.get()
        assert command.command_type == "move"
        assert command.from_position == "e2"
        assert command.to_position == "e4"

    @pytest.mark.asyncio
    async def test_handle_game_state_change(self, service):
        """测试处理游戏状态变化"""
        event_data = {
            "data": {
                "status": "finished"
            }
        }

        await service._handle_game_state_change(event_data)

        # 检查是否添加了home命令
        assert not service.command_queue.empty()
        command = await service.command_queue.get()
        assert command.command_type == "home"

    @pytest.mark.asyncio
    async def test_handle_emergency_stop(self, service, mock_controller):
        """测试处理紧急停止"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        # 添加一些命令到队列
        await service.command_queue.put(RobotCommand(command_type="move"))
        await service.command_queue.put(RobotCommand(command_type="pick"))

        await service._handle_emergency_stop({})

        # 检查控制器是否被停止
        mock_controller.emergency_stop.assert_called_once()

        # 检查队列是否被清空
        assert service.command_queue.empty()

    @pytest.mark.asyncio
    async def test_execute_command_move(self, service, mock_controller):
        """测试执行移动命令"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        command = RobotCommand(
            command_type="move",
            from_position="e2",
            to_position="e4"
        )

        result = await service._execute_command(command)

        assert result
        mock_controller.execute_move.assert_called_once_with("e2", "e4")

    @pytest.mark.asyncio
    async def test_execute_command_pick(self, service, mock_controller):
        """测试执行抓取命令"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        command = RobotCommand(
            command_type="pick",
            from_position="e4"
        )

        result = await service._execute_command(command)

        assert result
        mock_controller.pick_piece.assert_called_once_with("e4")

    @pytest.mark.asyncio
    async def test_execute_command_place(self, service, mock_controller):
        """测试执行放置命令"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        command = RobotCommand(
            command_type="place",
            to_position="e5"
        )

        result = await service._execute_command(command)

        assert result
        mock_controller.place_piece.assert_called_once_with("e5")

    @pytest.mark.asyncio
    async def test_execute_command_home(self, service, mock_controller):
        """测试执行回原点命令"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        command = RobotCommand(command_type="home")

        result = await service._execute_command(command)

        assert result
        mock_controller.home.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_stop(self, service, mock_controller):
        """测试执行停止命令"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        command = RobotCommand(command_type="stop")

        result = await service._execute_command(command)

        assert result
        mock_controller.emergency_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_unknown(self, service, mock_controller):
        """测试执行未知命令"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        command = RobotCommand(command_type="unknown")

        result = await service._execute_command(command)

        assert not result

    @pytest.mark.asyncio
    async def test_execute_command_missing_params(self, service, mock_controller):
        """测试执行缺少参数的命令"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        # 移动命令但缺少位置参数
        command = RobotCommand(command_type="move")

        result = await service._execute_command(command)

        assert not result

    @pytest.mark.asyncio
    async def test_publish_command_result(self, service):
        """测试发布命令结果"""
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        command = RobotCommand(command_type="move", from_position="e2", to_position="e4")

        await service._publish_command_result(command, True)

        service.event_bus.publish.assert_called_once()
        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "robot_command_result"
        assert call_args.data["success"] is True

    @pytest.mark.asyncio
    async def test_publish_status(self, service, mock_controller):
        """测试发布状态"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        await service._publish_status()

        service.event_bus.publish.assert_called_once()
        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "robot_status_update"
        assert call_args.source == "robot_service"

    @pytest.mark.asyncio
    async def test_shutdown(self, service, mock_controller, mock_event_bus):
        """测试服务关闭"""
        service.controller = mock_controller
        service.event_bus = mock_event_bus
        service.is_running = True

        await service.shutdown()

        assert not service.is_running
        mock_controller.disconnect.assert_called_once()
        mock_event_bus.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_command_processor(self, service, mock_controller):
        """测试命令处理器"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.is_running = True

        # 添加测试命令
        command = RobotCommand(command_type="home")
        await service.command_queue.put(command)

        # 运行一次处理循环
        with patch.object(service, '_execute_command', return_value=True) as mock_execute:
            # 创建任务并立即取消以结束循环
            task = asyncio.create_task(service._command_processor())
            await asyncio.sleep(0.1)  # 让处理器运行一次
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_reporter(self, service, mock_controller):
        """测试状态报告器"""
        service.controller = mock_controller
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.is_running = True

        # 运行一次报告循环
        with patch.object(service, '_publish_status') as mock_publish:
            task = asyncio.create_task(service._status_reporter())
            await asyncio.sleep(0.1)  # 让报告器运行一次
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            mock_publish.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
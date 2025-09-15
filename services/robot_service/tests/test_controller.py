"""
DofBot Pro控制器测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from shared.models.chess_models import Position3D, Position6D, RobotStatus
from services.robot_service.src.robot.controller import DofBotProController


class TestDofBotProController:
    """DofBot Pro控制器测试类"""

    @pytest.fixture
    def controller(self):
        """创建控制器实例"""
        return DofBotProController()

    @pytest.fixture
    def mock_serial(self):
        """模拟串口连接"""
        with patch('serial.Serial') as mock:
            mock.return_value.is_open = True
            mock.return_value.write = Mock()
            mock.return_value.readline = Mock(return_value=b"OK\r\n")
            mock.return_value.in_waiting = 4
            yield mock

    def test_init(self, controller):
        """测试初始化"""
        assert controller.port == "/dev/ttyUSB0"
        assert controller.baudrate == 115200
        assert not controller.is_connected
        assert not controller.is_moving
        assert len(controller.joint_angles) == 6
        assert len(controller.link_lengths) == 5
        assert len(controller.joint_limits) == 6

    @pytest.mark.asyncio
    async def test_initialize_success(self, controller, mock_serial):
        """测试初始化成功"""
        with patch.object(controller, '_send_command', return_value=True):
            success = await controller.initialize()

            assert success
            assert controller.is_connected

    @pytest.mark.asyncio
    async def test_initialize_failure(self, controller):
        """测试初始化失败"""
        with patch('serial.Serial', side_effect=Exception("连接失败")):
            success = await controller.initialize()

            assert not success
            assert not controller.is_connected

    @pytest.mark.asyncio
    async def test_send_command_success(self, controller, mock_serial):
        """测试发送命令成功"""
        controller.serial_conn = mock_serial.return_value

        result = await controller._send_command("TEST")

        assert result
        mock_serial.return_value.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_command_no_connection(self, controller):
        """测试无连接时发送命令"""
        result = await controller._send_command("TEST")

        assert not result

    def test_square_to_world_coords(self, controller):
        """测试棋盘坐标转换"""
        # 测试a1位置
        pos = controller._square_to_world_coords("a1")
        assert pos.x == -87.5
        assert pos.y == -87.5
        assert pos.z == 0.0

        # 测试h8位置
        pos = controller._square_to_world_coords("h8")
        assert pos.x == 87.5
        assert pos.y == 87.5

        # 测试e4位置（中心附近）
        pos = controller._square_to_world_coords("e4")
        assert pos.x == 12.5
        assert pos.y == -12.5

    def test_square_to_world_coords_invalid(self, controller):
        """测试无效棋盘坐标"""
        with pytest.raises(ValueError):
            controller._square_to_world_coords("i9")  # 超出棋盘范围

        with pytest.raises(ValueError):
            controller._square_to_world_coords("a")  # 格式错误

    def test_inverse_kinematics_reachable(self, controller):
        """测试逆运动学 - 可达位置"""
        pose = Position6D(100, 100, 150, 0, 0, 0)
        joints = controller._inverse_kinematics(pose)

        assert joints is not None
        assert len(joints) == 6
        assert all(isinstance(j, (int, float)) for j in joints)

    def test_inverse_kinematics_unreachable(self, controller):
        """测试逆运动学 - 不可达位置"""
        pose = Position6D(1000, 1000, 1000, 0, 0, 0)  # 超出工作空间
        joints = controller._inverse_kinematics(pose)

        assert joints is None

    def test_check_joint_limits_valid(self, controller):
        """测试关节限制 - 有效角度"""
        valid_angles = [0, 0, 0, 0, 0, 0]  # 所有关节在0度
        assert controller._check_joint_limits(valid_angles)

        valid_angles = [45, -45, 30, -30, 60, -60]
        assert controller._check_joint_limits(valid_angles)

    def test_check_joint_limits_invalid(self, controller):
        """测试关节限制 - 无效角度"""
        invalid_angles = [180, 0, 0, 0, 0, 0]  # 第一个关节超限
        assert not controller._check_joint_limits(invalid_angles)

        invalid_angles = [0, 150, 0, 0, 0, 0]  # 第二个关节超限
        assert not controller._check_joint_limits(invalid_angles)

    def test_plan_trajectory(self, controller):
        """测试轨迹规划"""
        start = [0, 0, 0, 0, 0, 0]
        end = [90, 45, 30, 15, 60, 30]

        trajectory = controller._plan_trajectory(start, end, steps=10)

        assert len(trajectory) == 11  # steps + 1
        assert trajectory[0] == start
        assert trajectory[-1] == end

        # 检查中间点
        mid_point = trajectory[5]
        expected_mid = [45, 22.5, 15, 7.5, 30, 15]
        for i in range(6):
            assert abs(mid_point[i] - expected_mid[i]) < 0.1

    def test_format_joint_command(self, controller):
        """测试关节命令格式化"""
        angles = [0, 90, -90, 45, -45, 0]
        command = controller._format_joint_command(angles)

        assert command.startswith("#000P1500")  # 第一个关节，0度 -> 1500微秒
        assert command.endswith("!")
        assert "#001P2000" in command  # 第二个关节，90度 -> 2000微秒
        assert "#002P1000" in command  # 第三个关节，-90度 -> 1000微秒

    @pytest.mark.asyncio
    async def test_home(self, controller):
        """测试回到原点"""
        with patch.object(controller, '_move_to_position', return_value=True):
            result = await controller.home()

            assert result
            assert controller.current_position.x == 0
            assert controller.current_position.y == 0
            assert controller.current_position.z == 0

    @pytest.mark.asyncio
    async def test_move_to_square(self, controller):
        """测试移动到棋盘位置"""
        with patch.object(controller, '_move_to_position', return_value=True):
            result = await controller.move_to_square("e4", height=20.0)

            assert result

    @pytest.mark.asyncio
    async def test_pick_piece(self, controller):
        """测试抓取棋子"""
        with patch.object(controller, 'move_to_square', return_value=True), \
             patch.object(controller, '_control_gripper', return_value=True):

            result = await controller.pick_piece("e4")

            assert result

    @pytest.mark.asyncio
    async def test_place_piece(self, controller):
        """测试放置棋子"""
        with patch.object(controller, 'move_to_square', return_value=True), \
             patch.object(controller, '_control_gripper', return_value=True):

            result = await controller.place_piece("e5")

            assert result

    @pytest.mark.asyncio
    async def test_execute_move(self, controller):
        """测试执行完整移动"""
        with patch.object(controller, 'pick_piece', return_value=True), \
             patch.object(controller, 'place_piece', return_value=True):

            result = await controller.execute_move("e2", "e4")

            assert result

    @pytest.mark.asyncio
    async def test_execute_move_failure(self, controller):
        """测试移动失败处理"""
        with patch.object(controller, 'pick_piece', return_value=True), \
             patch.object(controller, 'place_piece', side_effect=[False, True]):

            result = await controller.execute_move("e2", "e4")

            assert not result

    @pytest.mark.asyncio
    async def test_control_gripper(self, controller):
        """测试夹爪控制"""
        with patch.object(controller, '_send_command', return_value=True):
            # 测试夹紧
            result = await controller._control_gripper(True)
            assert result
            assert controller.gripper_state

            # 测试松开
            result = await controller._control_gripper(False)
            assert result
            assert not controller.gripper_state

    def test_get_status(self, controller):
        """测试获取状态"""
        controller.is_connected = True
        controller.is_moving = False
        controller.current_position = Position6D(10, 20, 30, 0, 0, 0)

        status = controller.get_status()

        assert isinstance(status, RobotStatus)
        assert status.is_connected
        assert not status.is_moving
        assert status.current_position.x == 10
        assert status.current_position.y == 20
        assert status.current_position.z == 30

    @pytest.mark.asyncio
    async def test_emergency_stop(self, controller):
        """测试紧急停止"""
        with patch.object(controller, '_send_command', return_value=True):
            controller.is_moving = True

            await controller.emergency_stop()

            assert not controller.is_moving


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
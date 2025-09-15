"""
DofBot Pro 6DOF机械臂控制器
"""
import asyncio
import json
import time
from typing import List, Optional, Dict, Any, Tuple
import serial
import numpy as np
from dataclasses import asdict
import logging

from shared.models.chess_models import Position3D, Position6D, RobotCommand, RobotStatus
from shared.utils.logger import get_logger
from shared.config.settings import get_settings

settings = get_settings()
logger = get_logger(__name__)


class DofBotProController:
    """DofBot Pro机械臂控制器"""

    def __init__(self):
        self.port = settings.robot.port
        self.baudrate = settings.robot.baudrate
        self.timeout = settings.robot.timeout
        self.default_speed = settings.robot.default_speed
        self.safe_height = settings.robot.safe_height

        self.serial_conn: Optional[serial.Serial] = None
        self.is_connected = False
        self.is_moving = False
        self.current_position = Position6D(0, 0, 0, 0, 0, 0)
        self.joint_angles = [0.0] * 6  # 6个关节角度
        self.gripper_state = False  # False=松开, True=夹紧
        self.last_command_time = 0.0

        # 机械臂物理参数 (DofBot Pro规格)
        self.link_lengths = [61.0, 43.5, 82.85, 82.85, 54.57]  # mm
        self.joint_limits = [
            (-135, 135),  # 基座旋转
            (-105, 105),  # 大臂抬升
            (-105, 105),  # 小臂抬升
            (-105, 105),  # 腕关节1
            (-135, 135),  # 腕关节2
            (-180, 180)   # 腕关节3
        ]
        self.max_velocity = 100  # 最大速度
        self.max_acceleration = 200  # 最大加速度

    async def initialize(self) -> bool:
        """初始化机械臂连接"""
        try:
            logger.info(f"正在连接DofBot Pro机械臂: {self.port}@{self.baudrate}")

            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )

            # 等待连接稳定
            await asyncio.sleep(2)

            # 发送初始化命令
            if await self._send_command("INIT"):
                self.is_connected = True
                logger.info("DofBot Pro机械臂连接成功")

                # 获取当前状态
                await self.update_status()
                return True
            else:
                logger.error("DofBot Pro机械臂初始化失败")
                return False

        except Exception as e:
            logger.error(f"连接DofBot Pro失败: {str(e)}")
            return False

    async def disconnect(self):
        """断开机械臂连接"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                logger.info("DofBot Pro机械臂连接已断开")
        except Exception as e:
            logger.error(f"断开连接时出错: {str(e)}")
        finally:
            self.is_connected = False

    async def _send_command(self, command: str) -> bool:
        """发送串口命令"""
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("串口连接未建立")
            return False

        try:
            # 添加命令结束符
            cmd_with_terminator = f"{command}\r\n"
            self.serial_conn.write(cmd_with_terminator.encode())

            # 等待响应
            response = ""
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                if self.serial_conn.in_waiting > 0:
                    response = self.serial_conn.readline().decode().strip()
                    break
                await asyncio.sleep(0.01)

            if response == "OK":
                self.last_command_time = time.time()
                return True
            else:
                logger.warning(f"命令响应异常: {response}")
                return False

        except Exception as e:
            logger.error(f"发送命令失败: {str(e)}")
            return False

    async def home(self) -> bool:
        """回到原点位置"""
        logger.info("机械臂回到原点")
        self.is_moving = True

        try:
            # 先升高到安全高度
            safe_position = Position6D(0, 0, self.safe_height, 0, 0, 0)
            if not await self._move_to_position(safe_position):
                return False

            # 回到原点
            home_position = Position6D(0, 0, 0, 0, 0, 0)
            success = await self._move_to_position(home_position)

            if success:
                self.current_position = home_position
                self.joint_angles = [0.0] * 6
                logger.info("机械臂已回到原点")

            return success

        except Exception as e:
            logger.error(f"回原点失败: {str(e)}")
            return False
        finally:
            self.is_moving = False

    async def move_to_square(self, square: str, height: float = 0.0) -> bool:
        """移动到指定棋盘位置"""
        try:
            # 将棋盘坐标转换为物理坐标
            world_pos = self._square_to_world_coords(square)
            world_pos.z = height

            logger.info(f"移动到棋盘位置 {square} -> ({world_pos.x:.1f}, {world_pos.y:.1f}, {world_pos.z:.1f})")

            return await self.move_to_position(world_pos)

        except Exception as e:
            logger.error(f"移动到 {square} 失败: {str(e)}")
            return False

    async def move_to_position(self, position: Position3D) -> bool:
        """移动到3D位置"""
        # 转换为6D位姿（默认垂直向下抓取）
        pose = Position6D(
            position.x, position.y, position.z,
            0, 0, 0  # 默认姿态
        )
        return await self._move_to_position(pose)

    async def _move_to_position(self, pose: Position6D) -> bool:
        """执行6D位姿移动"""
        self.is_moving = True

        try:
            # 逆运动学解算
            joint_angles = self._inverse_kinematics(pose)
            if joint_angles is None:
                logger.error(f"逆运动学求解失败: {pose}")
                return False

            # 检查关节限位
            if not self._check_joint_limits(joint_angles):
                logger.error("关节角度超出限制")
                return False

            # 轨迹规划
            trajectory = self._plan_trajectory(self.joint_angles, joint_angles)

            # 执行轨迹
            for waypoint in trajectory:
                cmd = self._format_joint_command(waypoint)
                if not await self._send_command(cmd):
                    logger.error("执行轨迹点失败")
                    return False

                # 等待运动完成
                await asyncio.sleep(0.1)

            # 更新当前状态
            self.joint_angles = joint_angles
            self.current_position = pose

            logger.info(f"成功移动到位置: ({pose.x:.1f}, {pose.y:.1f}, {pose.z:.1f})")
            return True

        except Exception as e:
            logger.error(f"移动失败: {str(e)}")
            return False
        finally:
            self.is_moving = False

    async def pick_piece(self, square: str) -> bool:
        """抓取棋子"""
        logger.info(f"抓取棋子: {square}")

        try:
            # 移动到目标上方
            if not await self.move_to_square(square, self.safe_height):
                return False

            # 下降到抓取高度
            if not await self.move_to_square(square, 5.0):  # 5mm高度抓取
                return False

            # 夹紧夹爪
            if not await self._control_gripper(True):
                return False

            # 提升到安全高度
            if not await self.move_to_square(square, self.safe_height):
                return False

            logger.info(f"成功抓取棋子: {square}")
            return True

        except Exception as e:
            logger.error(f"抓取棋子失败: {str(e)}")
            return False

    async def place_piece(self, square: str) -> bool:
        """放置棋子"""
        logger.info(f"放置棋子: {square}")

        try:
            # 移动到目标上方
            if not await self.move_to_square(square, self.safe_height):
                return False

            # 下降到放置高度
            if not await self.move_to_square(square, 5.0):
                return False

            # 松开夹爪
            if not await self._control_gripper(False):
                return False

            # 提升到安全高度
            if not await self.move_to_square(square, self.safe_height):
                return False

            logger.info(f"成功放置棋子: {square}")
            return True

        except Exception as e:
            logger.error(f"放置棋子失败: {str(e)}")
            return False

    async def execute_move(self, from_square: str, to_square: str) -> bool:
        """执行完整的移动操作"""
        logger.info(f"执行移动: {from_square} -> {to_square}")

        try:
            # 抓取棋子
            if not await self.pick_piece(from_square):
                return False

            # 放置棋子
            if not await self.place_piece(to_square):
                # 如果放置失败，尝试放回原位
                await self.place_piece(from_square)
                return False

            logger.info(f"移动完成: {from_square} -> {to_square}")
            return True

        except Exception as e:
            logger.error(f"执行移动失败: {str(e)}")
            return False

    async def _control_gripper(self, grip: bool) -> bool:
        """控制夹爪"""
        try:
            command = "GRIP_CLOSE" if grip else "GRIP_OPEN"
            if await self._send_command(command):
                self.gripper_state = grip
                await asyncio.sleep(0.5)  # 等待夹爪动作完成
                return True
            return False
        except Exception as e:
            logger.error(f"控制夹爪失败: {str(e)}")
            return False

    def _square_to_world_coords(self, square: str) -> Position3D:
        """将棋盘坐标转换为世界坐标"""
        if len(square) != 2:
            raise ValueError(f"无效的棋盘坐标: {square}")

        col = ord(square[0].lower()) - ord('a')  # a-h => 0-7
        row = int(square[1]) - 1                 # 1-8 => 0-7

        # 棋盘物理尺寸 (需要根据实际棋盘调整)
        square_size = 25.0  # mm
        board_origin_x = -87.5  # mm
        board_origin_y = -87.5  # mm

        world_x = board_origin_x + col * square_size
        world_y = board_origin_y + row * square_size

        return Position3D(world_x, world_y, 0.0)

    def _inverse_kinematics(self, pose: Position6D) -> Optional[List[float]]:
        """逆运动学求解 - DofBot Pro专用"""
        try:
            x, y, z = pose.x, pose.y, pose.z
            rx, ry, rz = pose.rx, pose.ry, pose.rz

            # 简化的逆运动学求解 (针对6DOF臂)
            # 这里使用几何方法求解，实际应用中可能需要更复杂的算法

            # 基座角度 (关节1)
            theta1 = np.arctan2(y, x)

            # 计算末端位置到基座的距离
            r = np.sqrt(x**2 + y**2)

            # 考虑末端偏移
            wrist_offset = self.link_lengths[4]  # 腕部长度
            xw = r - wrist_offset * np.cos(rz)
            zw = z - self.link_lengths[0] - wrist_offset * np.sin(rz)  # 减去基座高度

            # 大臂和小臂长度
            l2 = self.link_lengths[2]  # 大臂
            l3 = self.link_lengths[3]  # 小臂

            # 计算关节3角度 (小臂关节)
            cos_theta3 = (xw**2 + zw**2 - l2**2 - l3**2) / (2 * l2 * l3)
            if abs(cos_theta3) > 1:
                logger.error("目标位置超出工作空间")
                return None

            theta3 = np.arccos(cos_theta3)

            # 计算关节2角度 (大臂关节)
            k1 = l2 + l3 * np.cos(theta3)
            k2 = l3 * np.sin(theta3)
            theta2 = np.arctan2(zw, xw) - np.arctan2(k2, k1)

            # 腕部角度计算 (简化处理)
            theta4 = -(theta2 + theta3) + ry  # 保持末端姿态
            theta5 = rx
            theta6 = rz

            # 转换为度数
            joint_angles = [
                np.degrees(theta1),
                np.degrees(theta2),
                np.degrees(theta3),
                np.degrees(theta4),
                np.degrees(theta5),
                np.degrees(theta6)
            ]

            return joint_angles

        except Exception as e:
            logger.error(f"逆运动学求解失败: {str(e)}")
            return None

    def _check_joint_limits(self, joint_angles: List[float]) -> bool:
        """检查关节角度限制"""
        for i, angle in enumerate(joint_angles):
            min_angle, max_angle = self.joint_limits[i]
            if not (min_angle <= angle <= max_angle):
                logger.error(f"关节{i+1}角度超限: {angle}° (限制: {min_angle}°~{max_angle}°)")
                return False
        return True

    def _plan_trajectory(self, start_angles: List[float], end_angles: List[float],
                        steps: int = 20) -> List[List[float]]:
        """轨迹规划 - 简单线性插值"""
        trajectory = []
        for i in range(steps + 1):
            t = i / steps
            waypoint = []
            for j in range(len(start_angles)):
                angle = start_angles[j] + t * (end_angles[j] - start_angles[j])
                waypoint.append(angle)
            trajectory.append(waypoint)
        return trajectory

    def _format_joint_command(self, joint_angles: List[float]) -> str:
        """格式化关节角度命令"""
        # DofBot Pro命令格式: #000P1500T1000!
        # 其中000是舵机ID，1500是位置值，1000是时间
        commands = []
        for i, angle in enumerate(joint_angles):
            # 将角度转换为舵机脉宽值 (500-2500微秒)
            pulse_width = int(1500 + (angle / 180.0) * 1000)
            pulse_width = max(500, min(2500, pulse_width))  # 限制范围
            commands.append(f"#{i:03d}P{pulse_width}T1000")

        return "".join(commands) + "!"

    async def update_status(self) -> RobotStatus:
        """更新机器人状态"""
        try:
            # 查询当前关节角度
            if await self._send_command("GET_JOINTS"):
                # 这里应该解析返回的关节角度，简化处理
                pass

            return RobotStatus(
                is_connected=self.is_connected,
                is_moving=self.is_moving,
                current_position=self.current_position,
                joint_angles=self.joint_angles,
                gripper_state=self.gripper_state,
                last_update=time.time()
            )

        except Exception as e:
            logger.error(f"更新状态失败: {str(e)}")
            return RobotStatus(
                is_connected=False,
                is_moving=False,
                current_position=Position6D(0, 0, 0, 0, 0, 0),
                joint_angles=[0.0] * 6,
                gripper_state=False,
                error_message=str(e)
            )

    async def emergency_stop(self):
        """紧急停止"""
        logger.warning("执行紧急停止")
        try:
            await self._send_command("STOP")
            self.is_moving = False
        except Exception as e:
            logger.error(f"紧急停止失败: {str(e)}")

    def get_status(self) -> RobotStatus:
        """获取当前状态"""
        return RobotStatus(
            is_connected=self.is_connected,
            is_moving=self.is_moving,
            current_position=self.current_position,
            joint_angles=self.joint_angles,
            gripper_state=self.gripper_state,
            last_update=time.time()
        )
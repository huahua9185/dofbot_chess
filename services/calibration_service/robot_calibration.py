#!/usr/bin/env python3
"""
机械臂标定程序 - DofBot Pro 6DOF
用于标定机械臂的DH参数、关节零点和手眼标定
"""

import numpy as np
import json
import serial
import time
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import cv2
from scipy.optimize import minimize

@dataclass
class DHParameters:
    """DH参数"""
    a: float      # 连杆长度
    d: float      # 连杆偏移
    alpha: float  # 连杆扭转角
    theta: float  # 关节角度


@dataclass
class RobotConfig:
    """机器人配置"""
    joint_limits: List[Tuple[float, float]]  # 关节限位
    home_position: List[float]               # 零点位置
    dh_params: List[DHParameters]            # DH参数
    tcp_offset: List[float]                  # 工具中心点偏移


class RobotCalibration:
    """机械臂标定类"""

    def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 115200):
        """
        初始化标定参数

        Args:
            port: 串口端口
            baudrate: 波特率
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None

        # DofBot Pro 默认DH参数（单位：mm）
        self.default_dh_params = [
            DHParameters(a=0, d=105, alpha=np.pi/2, theta=0),     # Joint 1
            DHParameters(a=105, d=0, alpha=0, theta=np.pi/2),     # Joint 2
            DHParameters(a=98, d=0, alpha=0, theta=0),            # Joint 3
            DHParameters(a=0, d=0, alpha=np.pi/2, theta=0),       # Joint 4
            DHParameters(a=0, d=155, alpha=-np.pi/2, theta=0),    # Joint 5
            DHParameters(a=0, d=0, alpha=0, theta=0),             # Joint 6
        ]

        # 关节限位（弧度）
        self.joint_limits = [
            (-np.pi, np.pi),        # Joint 1: ±180°
            (-np.pi/2, np.pi/2),    # Joint 2: ±90°
            (-np.pi/2, np.pi/2),    # Joint 3: ±90°
            (-np.pi/2, np.pi/2),    # Joint 4: ±90°
            (-np.pi/2, np.pi/2),    # Joint 5: ±90°
            (-np.pi, np.pi),        # Joint 6: ±180°
        ]

        # 标定数据
        self.calibration_points = []
        self.measured_positions = []
        self.camera_poses = []
        self.robot_poses = []

        # 标定结果
        self.calibrated_dh_params = None
        self.tcp_offset = np.array([0, 0, 45])  # 夹爪长度 mm
        self.hand_eye_matrix = None

        # 保存路径
        self.calibration_dir = Path("/home/jetson/prog/data/calibration")
        self.calibration_dir.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """连接机械臂"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            time.sleep(2.0)  # 等待连接稳定
            print(f"成功连接到机械臂: {self.port}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None
            print("已断开机械臂连接")

    def send_command(self, command: str) -> Optional[str]:
        """发送命令到机械臂"""
        if not self.serial_conn:
            print("机械臂未连接")
            return None

        try:
            self.serial_conn.write(command.encode('utf-8'))
            time.sleep(0.1)
            response = self.serial_conn.readline().decode('utf-8').strip()
            return response
        except Exception as e:
            print(f"命令发送失败: {e}")
            return None

    def get_joint_positions(self) -> Optional[List[float]]:
        """获取当前关节位置"""
        response = self.send_command("GET_JOINT_POS\n")
        if response:
            try:
                positions = [float(x) for x in response.split(',')]
                return positions
            except:
                return None
        return None

    def move_to_joint(self, joint_positions: List[float], speed: int = 50):
        """
        移动到指定关节位置

        Args:
            joint_positions: 6个关节的目标位置（弧度）
            speed: 移动速度 (0-100)
        """
        # 检查关节限位
        for i, pos in enumerate(joint_positions):
            min_limit, max_limit = self.joint_limits[i]
            if pos < min_limit or pos > max_limit:
                print(f"关节 {i+1} 超出限位: {pos}")
                return False

        # 发送移动命令
        positions_deg = [np.degrees(pos) for pos in joint_positions]
        command = f"MOVE_JOINT {','.join(map(str, positions_deg))},{speed}\n"
        response = self.send_command(command)
        time.sleep(2.0)  # 等待移动完成
        return response is not None

    def calibrate_home_position(self):
        """标定零点位置"""
        print("\n=== 零点标定 ===")
        print("请手动将机械臂移动到零点位置")
        print("零点定义：所有关节归零，机械臂垂直向上")
        input("按回车键确认零点位置...")

        current_pos = self.get_joint_positions()
        if current_pos:
            print(f"当前位置: {current_pos}")
            confirm = input("确认设置为零点？(y/n): ")
            if confirm.lower() == 'y':
                self.send_command("SET_HOME\n")
                print("零点设置成功")
                return current_pos
        return None

    def calibrate_dh_parameters(self, num_samples: int = 50):
        """
        标定DH参数

        Args:
            num_samples: 采样点数量
        """
        print("\n=== DH参数标定 ===")
        print(f"将采集 {num_samples} 个位置进行标定")

        calibration_data = []

        for i in range(num_samples):
            # 生成随机关节位置
            random_joints = []
            for limits in self.joint_limits:
                pos = np.random.uniform(limits[0] * 0.7, limits[1] * 0.7)
                random_joints.append(pos)

            # 移动到位置
            print(f"移动到采样点 {i+1}/{num_samples}")
            if self.move_to_joint(random_joints):
                time.sleep(1.0)

                # 获取实际位置
                actual_pos = self.get_joint_positions()
                if actual_pos:
                    # 计算理论末端位置
                    theoretical_pose = self.forward_kinematics(random_joints)

                    # 这里需要外部测量实际末端位置
                    print("请测量末端执行器实际位置 (x, y, z) mm:")
                    try:
                        x = float(input("X: "))
                        y = float(input("Y: "))
                        z = float(input("Z: "))
                        measured_pose = np.array([x, y, z])

                        calibration_data.append({
                            'joints': actual_pos,
                            'theoretical': theoretical_pose[:3, 3],
                            'measured': measured_pose
                        })
                    except:
                        print("输入无效，跳过此点")

        # 优化DH参数
        if len(calibration_data) > 10:
            self._optimize_dh_parameters(calibration_data)

    def _optimize_dh_parameters(self, calibration_data: List[Dict]):
        """
        优化DH参数以最小化位置误差

        Args:
            calibration_data: 标定数据
        """
        print("\n开始优化DH参数...")

        # 初始参数
        initial_params = []
        for dh in self.default_dh_params:
            initial_params.extend([dh.a, dh.d, dh.alpha])

        def objective_function(params):
            """目标函数：最小化位置误差"""
            # 重构DH参数
            dh_params = []
            for i in range(6):
                idx = i * 3
                dh_params.append(DHParameters(
                    a=params[idx],
                    d=params[idx + 1],
                    alpha=params[idx + 2],
                    theta=0
                ))

            # 计算总误差
            total_error = 0
            for data in calibration_data:
                # 使用新DH参数计算正运动学
                pose = self.forward_kinematics_with_dh(data['joints'], dh_params)
                theoretical = pose[:3, 3]
                measured = data['measured']
                error = np.linalg.norm(theoretical - measured)
                total_error += error

            return total_error / len(calibration_data)

        # 优化
        result = minimize(
            objective_function,
            initial_params,
            method='BFGS',
            options={'maxiter': 1000}
        )

        if result.success:
            print(f"优化成功，平均误差: {result.fun:.2f} mm")

            # 更新DH参数
            self.calibrated_dh_params = []
            for i in range(6):
                idx = i * 3
                self.calibrated_dh_params.append(DHParameters(
                    a=result.x[idx],
                    d=result.x[idx + 1],
                    alpha=result.x[idx + 2],
                    theta=0
                ))

            # 保存标定结果
            self._save_dh_parameters()
        else:
            print("优化失败")

    def calibrate_hand_eye(self, camera_calibration_file: str):
        """
        手眼标定 - 计算相机与机械臂末端的变换关系

        Args:
            camera_calibration_file: 相机标定文件路径
        """
        print("\n=== 手眼标定 ===")
        print("将采集多个位置的棋盘格图像进行手眼标定")

        # 加载相机标定参数
        with open(camera_calibration_file, 'r') as f:
            camera_data = json.load(f)
            camera_matrix = np.array(camera_data['camera_matrix'])
            dist_coeffs = np.array(camera_data['distortion_coefficients'])

        # 准备棋盘格
        board_size = (9, 6)
        square_size = 25.0  # mm

        # 采集数据
        num_poses = 15
        R_gripper2base = []
        t_gripper2base = []
        R_target2cam = []
        t_target2cam = []

        cap = cv2.VideoCapture(0)

        for i in range(num_poses):
            print(f"\n位置 {i+1}/{num_poses}")

            # 生成随机位置
            random_joints = []
            for limits in self.joint_limits:
                pos = np.random.uniform(limits[0] * 0.5, limits[1] * 0.5)
                random_joints.append(pos)

            # 移动机械臂
            if not self.move_to_joint(random_joints):
                continue

            time.sleep(2.0)

            # 获取机械臂位姿
            robot_pose = self.forward_kinematics(random_joints)
            R_gripper2base.append(robot_pose[:3, :3])
            t_gripper2base.append(robot_pose[:3, 3])

            # 捕获图像并检测棋盘格
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ret, corners = cv2.findChessboardCorners(gray, board_size, None)

            if ret:
                # 精细化角点
                corners = cv2.cornerSubPix(
                    gray, corners, (11, 11), (-1, -1),
                    criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                )

                # 计算棋盘格位姿
                objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
                objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2)
                objp *= square_size

                ret, rvec, tvec = cv2.solvePnP(objp, corners, camera_matrix, dist_coeffs)

                if ret:
                    R, _ = cv2.Rodrigues(rvec)
                    R_target2cam.append(R)
                    t_target2cam.append(tvec.flatten())
                    print(f"成功检测棋盘格")

        cap.release()

        if len(R_gripper2base) >= 3:
            # 执行手眼标定
            print("\n计算手眼变换矩阵...")
            R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
                R_gripper2base,
                t_gripper2base,
                R_target2cam,
                t_target2cam,
                method=cv2.CALIB_HAND_EYE_TSAI
            )

            self.hand_eye_matrix = np.eye(4)
            self.hand_eye_matrix[:3, :3] = R_cam2gripper
            self.hand_eye_matrix[:3, 3] = t_cam2gripper.flatten()

            print(f"手眼标定完成")
            print(f"变换矩阵:\n{self.hand_eye_matrix}")

            # 保存结果
            self._save_hand_eye_calibration()

    def forward_kinematics(self, joint_angles: List[float]) -> np.ndarray:
        """
        正运动学计算

        Args:
            joint_angles: 关节角度（弧度）

        Returns:
            4x4变换矩阵
        """
        dh_params = self.calibrated_dh_params if self.calibrated_dh_params else self.default_dh_params
        return self.forward_kinematics_with_dh(joint_angles, dh_params)

    def forward_kinematics_with_dh(self, joint_angles: List[float], dh_params: List[DHParameters]) -> np.ndarray:
        """
        使用指定DH参数计算正运动学

        Args:
            joint_angles: 关节角度（弧度）
            dh_params: DH参数列表

        Returns:
            4x4变换矩阵
        """
        T = np.eye(4)

        for i, (angle, dh) in enumerate(zip(joint_angles, dh_params)):
            theta = dh.theta + angle
            alpha = dh.alpha
            a = dh.a
            d = dh.d

            # DH变换矩阵
            Ti = np.array([
                [np.cos(theta), -np.sin(theta)*np.cos(alpha), np.sin(theta)*np.sin(alpha), a*np.cos(theta)],
                [np.sin(theta), np.cos(theta)*np.cos(alpha), -np.cos(theta)*np.sin(alpha), a*np.sin(theta)],
                [0, np.sin(alpha), np.cos(alpha), d],
                [0, 0, 0, 1]
            ])

            T = T @ Ti

        # 添加TCP偏移
        tcp_transform = np.eye(4)
        tcp_transform[:3, 3] = self.tcp_offset
        T = T @ tcp_transform

        return T

    def _save_dh_parameters(self):
        """保存DH参数"""
        data = {
            'dh_parameters': [],
            'tcp_offset': self.tcp_offset.tolist(),
            'joint_limits': self.joint_limits,
            'calibration_date': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        for dh in self.calibrated_dh_params:
            data['dh_parameters'].append({
                'a': dh.a,
                'd': dh.d,
                'alpha': dh.alpha,
                'theta': dh.theta
            })

        filepath = self.calibration_dir / 'robot_dh_parameters.json'
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"DH参数已保存到: {filepath}")

    def _save_hand_eye_calibration(self):
        """保存手眼标定结果"""
        data = {
            'hand_eye_matrix': self.hand_eye_matrix.tolist(),
            'calibration_date': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        filepath = self.calibration_dir / 'hand_eye_calibration.json'
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"手眼标定结果已保存到: {filepath}")

    def load_calibration(self) -> bool:
        """加载标定数据"""
        # 加载DH参数
        dh_filepath = self.calibration_dir / 'robot_dh_parameters.json'
        if dh_filepath.exists():
            with open(dh_filepath, 'r') as f:
                data = json.load(f)
                self.calibrated_dh_params = []
                for dh_data in data['dh_parameters']:
                    self.calibrated_dh_params.append(DHParameters(
                        a=dh_data['a'],
                        d=dh_data['d'],
                        alpha=dh_data['alpha'],
                        theta=dh_data['theta']
                    ))
                self.tcp_offset = np.array(data['tcp_offset'])
                print("DH参数加载成功")

        # 加载手眼标定
        he_filepath = self.calibration_dir / 'hand_eye_calibration.json'
        if he_filepath.exists():
            with open(he_filepath, 'r') as f:
                data = json.load(f)
                self.hand_eye_matrix = np.array(data['hand_eye_matrix'])
                print("手眼标定数据加载成功")

        return True

    def verify_calibration(self):
        """验证标定精度"""
        print("\n=== 标定验证 ===")

        if not self.connect():
            return

        # 测试几个位置
        test_positions = [
            [0, 0, 0, 0, 0, 0],  # 零点
            [np.pi/4, 0, 0, 0, 0, 0],  # 关节1旋转45度
            [0, np.pi/4, 0, 0, 0, 0],  # 关节2旋转45度
            [np.pi/6, np.pi/6, np.pi/6, 0, 0, 0],  # 多关节组合
        ]

        for i, pos in enumerate(test_positions):
            print(f"\n测试位置 {i+1}: {[np.degrees(p) for p in pos]} 度")

            # 移动到位置
            if self.move_to_joint(pos):
                time.sleep(2.0)

                # 获取实际位置
                actual_pos = self.get_joint_positions()
                if actual_pos:
                    # 计算理论末端位置
                    theoretical_pose = self.forward_kinematics(actual_pos)
                    position = theoretical_pose[:3, 3]
                    print(f"理论末端位置: X={position[0]:.1f}, Y={position[1]:.1f}, Z={position[2]:.1f} mm")

                    # 这里可以添加实际测量对比
                    measured = input("输入实测位置 (x,y,z) 或回车跳过: ")
                    if measured:
                        try:
                            x, y, z = map(float, measured.split(','))
                            error = np.linalg.norm(position - np.array([x, y, z]))
                            print(f"位置误差: {error:.2f} mm")
                        except:
                            print("输入格式错误")

        self.disconnect()


def main():
    """主函数 - 执行机械臂标定流程"""
    calibrator = RobotCalibration()

    print("=== DofBot Pro 机械臂标定程序 ===")
    print("1. 连接机械臂")
    print("2. 标定零点")
    print("3. 标定DH参数")
    print("4. 手眼标定")
    print("5. 验证标定")
    print("6. 加载标定数据")
    print("0. 退出")

    while True:
        choice = input("\n请选择操作: ")

        if choice == '1':
            calibrator.connect()

        elif choice == '2':
            if calibrator.serial_conn:
                calibrator.calibrate_home_position()
            else:
                print("请先连接机械臂")

        elif choice == '3':
            if calibrator.serial_conn:
                num_samples = int(input("输入采样点数量 (建议30-50): "))
                calibrator.calibrate_dh_parameters(num_samples)
            else:
                print("请先连接机械臂")

        elif choice == '4':
            camera_file = input("输入相机标定文件路径: ")
            if Path(camera_file).exists():
                calibrator.calibrate_hand_eye(camera_file)
            else:
                print("相机标定文件不存在")

        elif choice == '5':
            calibrator.verify_calibration()

        elif choice == '6':
            calibrator.load_calibration()

        elif choice == '0':
            calibrator.disconnect()
            break

        else:
            print("无效选择")


if __name__ == "__main__":
    main()
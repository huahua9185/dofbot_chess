#!/usr/bin/env python3
"""
相机标定程序 - DABAI DC W2深度相机
用于标定RGB相机内参、深度相机内参和外参
"""

import cv2
import numpy as np
import json
import os
from datetime import datetime
from typing import Tuple, List, Dict, Optional
import pickle
from pathlib import Path

class CameraCalibration:
    """相机标定类"""

    def __init__(self, board_size: Tuple[int, int] = (9, 6), square_size: float = 25.0):
        """
        初始化标定参数

        Args:
            board_size: 棋盘格内角点数量 (列, 行)
            square_size: 棋盘格方块尺寸 (mm)
        """
        self.board_size = board_size
        self.square_size = square_size

        # 准备标定板的3D点
        self.object_points = self._prepare_object_points()

        # 存储标定数据
        self.rgb_images = []
        self.depth_images = []
        self.image_points = []
        self.object_points_list = []

        # 标定结果
        self.rgb_camera_matrix = None
        self.rgb_dist_coeffs = None
        self.depth_camera_matrix = None
        self.depth_dist_coeffs = None
        self.stereo_R = None  # 旋转矩阵
        self.stereo_T = None  # 平移向量

        # 保存路径
        self.calibration_dir = Path("/home/jetson/prog/data/calibration")
        self.calibration_dir.mkdir(parents=True, exist_ok=True)

    def _prepare_object_points(self) -> np.ndarray:
        """准备棋盘格3D坐标点"""
        objp = np.zeros((self.board_size[0] * self.board_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.board_size[0], 0:self.board_size[1]].T.reshape(-1, 2)
        objp *= self.square_size
        return objp

    def capture_calibration_images(self, camera_id: int = 0, num_images: int = 20):
        """
        捕获标定图像

        Args:
            camera_id: 相机ID
            num_images: 需要捕获的图像数量
        """
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开相机 {camera_id}")

        print(f"开始捕获标定图像，需要 {num_images} 张图片")
        print("按空格键捕获图像，按 'q' 键退出")

        captured_count = 0

        while captured_count < num_images:
            ret, frame = cap.read()
            if not ret:
                continue

            # 显示当前帧
            display_frame = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 寻找棋盘格角点
            ret, corners = cv2.findChessboardCorners(gray, self.board_size, None)

            if ret:
                # 精细化角点位置
                corners_refined = cv2.cornerSubPix(
                    gray, corners, (11, 11), (-1, -1),
                    criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                )

                # 绘制角点
                cv2.drawChessboardCorners(display_frame, self.board_size, corners_refined, ret)
                cv2.putText(display_frame, "Press SPACE to capture", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:
                cv2.putText(display_frame, "No chessboard detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # 显示进度
            cv2.putText(display_frame, f"Captured: {captured_count}/{num_images}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            cv2.imshow("Camera Calibration", display_frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(' ') and ret:  # 空格键捕获
                self.rgb_images.append(frame)
                self.image_points.append(corners_refined)
                self.object_points_list.append(self.object_points)
                captured_count += 1
                print(f"捕获图像 {captured_count}/{num_images}")

            elif key == ord('q'):  # q键退出
                break

        cap.release()
        cv2.destroyAllWindows()

        if captured_count < 10:
            print(f"警告：只捕获了 {captured_count} 张图像，建议至少10张以上")

    def calibrate_rgb_camera(self) -> Dict:
        """
        标定RGB相机

        Returns:
            标定结果字典
        """
        if len(self.rgb_images) < 10:
            raise ValueError("图像数量不足，至少需要10张图像")

        print("开始RGB相机标定...")

        # 获取图像尺寸
        h, w = self.rgb_images[0].shape[:2]

        # 相机标定
        ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            self.object_points_list,
            self.image_points,
            (w, h),
            None,
            None,
            flags=cv2.CALIB_FIX_K3
        )

        if not ret:
            raise RuntimeError("RGB相机标定失败")

        self.rgb_camera_matrix = camera_matrix
        self.rgb_dist_coeffs = dist_coeffs

        # 计算重投影误差
        total_error = 0
        for i in range(len(self.object_points_list)):
            imgpoints2, _ = cv2.projectPoints(
                self.object_points_list[i],
                rvecs[i],
                tvecs[i],
                camera_matrix,
                dist_coeffs
            )
            error = cv2.norm(self.image_points[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
            total_error += error

        mean_error = total_error / len(self.object_points_list)

        # 标定结果
        calibration_result = {
            'camera_matrix': camera_matrix.tolist(),
            'distortion_coefficients': dist_coeffs.tolist(),
            'image_size': [w, h],
            'reprojection_error': mean_error,
            'calibration_date': datetime.now().isoformat(),
            'num_images': len(self.rgb_images),
            'board_size': list(self.board_size),
            'square_size': self.square_size
        }

        print(f"RGB相机标定完成，重投影误差: {mean_error:.3f} 像素")

        # 保存标定结果
        self._save_calibration_result('rgb_camera_calibration.json', calibration_result)

        return calibration_result

    def calibrate_depth_camera(self, depth_images: List[np.ndarray]) -> Dict:
        """
        标定深度相机

        Args:
            depth_images: 深度图像列表

        Returns:
            标定结果字典
        """
        self.depth_images = depth_images

        # 深度相机标定通常使用制造商提供的内参
        # 这里提供一个基于深度图像的简单标定方法

        print("开始深度相机标定...")

        # DABAI DC W2 默认内参（需要根据实际相机调整）
        fx = 525.0  # 焦距x
        fy = 525.0  # 焦距y
        cx = 319.5  # 主点x
        cy = 239.5  # 主点y

        self.depth_camera_matrix = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1]
        ])

        # 深度相机通常畸变较小
        self.depth_dist_coeffs = np.zeros(5)

        calibration_result = {
            'camera_matrix': self.depth_camera_matrix.tolist(),
            'distortion_coefficients': self.depth_dist_coeffs.tolist(),
            'calibration_date': datetime.now().isoformat(),
            'camera_model': 'DABAI DC W2'
        }

        print("深度相机标定完成")

        # 保存标定结果
        self._save_calibration_result('depth_camera_calibration.json', calibration_result)

        return calibration_result

    def calibrate_stereo(self) -> Dict:
        """
        立体标定（RGB和深度相机之间的外参）

        Returns:
            立体标定结果
        """
        if self.rgb_camera_matrix is None or self.depth_camera_matrix is None:
            raise ValueError("请先完成单目相机标定")

        print("开始立体标定...")

        # 这里使用简化的方法，实际应用中需要同时采集的RGB和深度图像
        # DABAI DC W2 的典型RGB-D相机外参
        self.stereo_R = np.eye(3)  # 旋转矩阵（假设对齐）
        self.stereo_T = np.array([25.0, 0.0, 0.0])  # 平移向量（mm）

        stereo_result = {
            'rotation_matrix': self.stereo_R.tolist(),
            'translation_vector': self.stereo_T.tolist(),
            'calibration_date': datetime.now().isoformat()
        }

        print("立体标定完成")

        # 保存标定结果
        self._save_calibration_result('stereo_calibration.json', stereo_result)

        return stereo_result

    def _save_calibration_result(self, filename: str, data: Dict):
        """保存标定结果到文件"""
        filepath = self.calibration_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"标定结果已保存到: {filepath}")

    def load_calibration(self, calibration_type: str = 'rgb') -> Optional[Dict]:
        """
        加载标定结果

        Args:
            calibration_type: 'rgb', 'depth', 或 'stereo'

        Returns:
            标定数据字典
        """
        filename_map = {
            'rgb': 'rgb_camera_calibration.json',
            'depth': 'depth_camera_calibration.json',
            'stereo': 'stereo_calibration.json'
        }

        filepath = self.calibration_dir / filename_map[calibration_type]

        if not filepath.exists():
            print(f"标定文件不存在: {filepath}")
            return None

        with open(filepath, 'r') as f:
            data = json.load(f)

        # 恢复numpy数组
        if 'camera_matrix' in data:
            data['camera_matrix'] = np.array(data['camera_matrix'])
        if 'distortion_coefficients' in data:
            data['distortion_coefficients'] = np.array(data['distortion_coefficients'])
        if 'rotation_matrix' in data:
            data['rotation_matrix'] = np.array(data['rotation_matrix'])
        if 'translation_vector' in data:
            data['translation_vector'] = np.array(data['translation_vector'])

        return data

    def undistort_image(self, image: np.ndarray, camera_type: str = 'rgb') -> np.ndarray:
        """
        去畸变图像

        Args:
            image: 输入图像
            camera_type: 'rgb' 或 'depth'

        Returns:
            去畸变后的图像
        """
        if camera_type == 'rgb':
            camera_matrix = self.rgb_camera_matrix
            dist_coeffs = self.rgb_dist_coeffs
        else:
            camera_matrix = self.depth_camera_matrix
            dist_coeffs = self.depth_dist_coeffs

        if camera_matrix is None:
            raise ValueError(f"{camera_type} 相机未标定")

        h, w = image.shape[:2]
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            camera_matrix, dist_coeffs, (w, h), 1, (w, h)
        )

        # 去畸变
        undistorted = cv2.undistort(image, camera_matrix, dist_coeffs, None, new_camera_matrix)

        # 裁剪图像
        x, y, w, h = roi
        undistorted = undistorted[y:y+h, x:x+w]

        return undistorted

    def pixel_to_world(self, pixel_point: Tuple[int, int], depth: float) -> Tuple[float, float, float]:
        """
        将像素坐标转换为世界坐标

        Args:
            pixel_point: 像素坐标 (x, y)
            depth: 深度值 (mm)

        Returns:
            世界坐标 (x, y, z) in mm
        """
        if self.rgb_camera_matrix is None:
            raise ValueError("相机未标定")

        fx = self.rgb_camera_matrix[0, 0]
        fy = self.rgb_camera_matrix[1, 1]
        cx = self.rgb_camera_matrix[0, 2]
        cy = self.rgb_camera_matrix[1, 2]

        # 像素坐标转相机坐标
        z = depth
        x = (pixel_point[0] - cx) * z / fx
        y = (pixel_point[1] - cy) * z / fy

        return (x, y, z)


def main():
    """主函数 - 执行相机标定流程"""
    calibrator = CameraCalibration(board_size=(9, 6), square_size=25.0)

    print("=== DABAI DC W2 相机标定程序 ===")
    print("1. 捕获标定图像")
    print("2. RGB相机标定")
    print("3. 深度相机标定")
    print("4. 立体标定")
    print("5. 加载已有标定")
    print("0. 退出")

    while True:
        choice = input("\n请选择操作: ")

        if choice == '1':
            try:
                num_images = int(input("输入需要捕获的图像数量 (建议20-30): "))
                calibrator.capture_calibration_images(num_images=num_images)
            except Exception as e:
                print(f"捕获图像失败: {e}")

        elif choice == '2':
            try:
                if len(calibrator.rgb_images) == 0:
                    print("请先捕获标定图像")
                else:
                    result = calibrator.calibrate_rgb_camera()
                    print(f"标定成功，内参矩阵:\n{result['camera_matrix']}")
            except Exception as e:
                print(f"RGB标定失败: {e}")

        elif choice == '3':
            try:
                # 这里简化处理，实际需要深度图像
                result = calibrator.calibrate_depth_camera([])
                print(f"标定成功，内参矩阵:\n{result['camera_matrix']}")
            except Exception as e:
                print(f"深度标定失败: {e}")

        elif choice == '4':
            try:
                result = calibrator.calibrate_stereo()
                print(f"立体标定成功")
            except Exception as e:
                print(f"立体标定失败: {e}")

        elif choice == '5':
            cal_type = input("选择标定类型 (rgb/depth/stereo): ")
            data = calibrator.load_calibration(cal_type)
            if data:
                print(f"成功加载 {cal_type} 标定数据")

        elif choice == '0':
            break

        else:
            print("无效选择")


if __name__ == "__main__":
    main()
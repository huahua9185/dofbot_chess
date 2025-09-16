"""
标定服务单元测试
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import cv2

from services.calibration_service.camera_calibration import CameraCalibration
from services.calibration_service.robot_calibration import RobotCalibration


class TestCameraCalibration:
    """相机标定测试类"""

    @pytest.fixture
    def calibrator(self):
        """创建相机标定实例"""
        return CameraCalibration(board_size=(9, 6), square_size=25.0)

    @pytest.fixture
    def mock_camera(self):
        """模拟相机"""
        camera = Mock()
        camera.read = Mock(return_value=(True, np.zeros((480, 640, 3), dtype=np.uint8)))
        camera.isOpened = Mock(return_value=True)
        camera.release = Mock()
        return camera

    def test_init(self, calibrator):
        """测试初始化"""
        assert calibrator.board_size == (9, 6)
        assert calibrator.square_size == 25.0
        assert calibrator.criteria is not None
        assert len(calibrator.obj_points) == 0
        assert len(calibrator.img_points) == 0

    def test_prepare_object_points(self, calibrator):
        """测试准备物体点"""
        obj_p = calibrator._prepare_object_points()

        assert obj_p.shape == (54, 3)  # 9*6 = 54 points
        assert obj_p[0, 2] == 0.0  # Z coordinate should be 0
        assert obj_p[1, 0] == 25.0  # X step should be square_size
        assert obj_p[9, 1] == 25.0  # Y step should be square_size

    @pytest.mark.asyncio
    async def test_capture_calibration_images_success(self, calibrator):
        """测试捕获标定图像成功"""
        with patch('cv2.VideoCapture') as mock_cap, \
             patch('cv2.findChessboardCorners') as mock_find:

            mock_cap.return_value.isOpened.return_value = True
            mock_cap.return_value.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
            mock_find.return_value = (True, np.random.rand(54, 1, 2).astype(np.float32))

            success = await calibrator.capture_calibration_images(num_images=5)

            assert success
            assert len(calibrator.img_points) == 5
            assert len(calibrator.obj_points) == 5

    @pytest.mark.asyncio
    async def test_capture_calibration_images_camera_failure(self, calibrator):
        """测试相机打开失败"""
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap.return_value.isOpened.return_value = False

            success = await calibrator.capture_calibration_images(num_images=5)

            assert not success
            assert len(calibrator.img_points) == 0

    def test_calibrate_rgb_camera_success(self, calibrator):
        """测试RGB相机标定成功"""
        # 准备测试数据
        calibrator.obj_points = [calibrator._prepare_object_points() for _ in range(10)]
        calibrator.img_points = [np.random.rand(54, 1, 2).astype(np.float32) for _ in range(10)]
        calibrator.image_size = (640, 480)

        with patch('cv2.calibrateCamera') as mock_calibrate:
            mock_calibrate.return_value = (
                0.5,  # reprojection error
                np.eye(3),  # camera matrix
                np.zeros(5),  # distortion coefficients
                None, None  # rvecs, tvecs
            )

            result = calibrator.calibrate_rgb_camera()

            assert result["success"]
            assert result["reprojection_error"] == 0.5
            assert "camera_matrix" in result
            assert "distortion_coefficients" in result

    def test_calibrate_rgb_camera_insufficient_data(self, calibrator):
        """测试数据不足时的标定"""
        # 只有少量数据点
        calibrator.obj_points = [calibrator._prepare_object_points() for _ in range(3)]
        calibrator.img_points = [np.random.rand(54, 1, 2).astype(np.float32) for _ in range(3)]

        result = calibrator.calibrate_rgb_camera()

        assert not result["success"]
        assert "error" in result

    def test_calibrate_stereo_cameras_success(self, calibrator):
        """测试立体相机标定成功"""
        # 准备测试数据
        calibrator.obj_points = [calibrator._prepare_object_points() for _ in range(10)]
        left_points = [np.random.rand(54, 1, 2).astype(np.float32) for _ in range(10)]
        right_points = [np.random.rand(54, 1, 2).astype(np.float32) for _ in range(10)]

        # 模拟已标定的相机参数
        camera_matrix = np.eye(3)
        dist_coeffs = np.zeros(5)
        image_size = (640, 480)

        with patch('cv2.stereoCalibrate') as mock_stereo:
            mock_stereo.return_value = (
                0.3,  # reprojection error
                camera_matrix, dist_coeffs,  # left camera
                camera_matrix, dist_coeffs,  # right camera
                np.eye(3),  # R
                np.array([100, 0, 0]),  # T
                np.eye(3), np.array([0, 0, 0])  # E, F
            )

            result = calibrator.calibrate_stereo_cameras(
                left_points, right_points,
                camera_matrix, dist_coeffs,
                camera_matrix, dist_coeffs,
                image_size
            )

            assert result["success"]
            assert result["stereo_reprojection_error"] == 0.3
            assert "R" in result
            assert "T" in result

    def test_undistort_image(self, calibrator):
        """测试图像去畸变"""
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        camera_matrix = np.eye(3)
        dist_coeffs = np.zeros(5)

        with patch('cv2.undistort') as mock_undistort:
            mock_undistort.return_value = image

            result = calibrator.undistort_image(image, camera_matrix, dist_coeffs)

            assert result.shape == image.shape
            mock_undistort.assert_called_once()

    def test_pixel_to_world_coordinates(self, calibrator):
        """测试像素到世界坐标转换"""
        pixel_point = (320, 240)
        depth = 1000.0  # mm
        camera_matrix = np.array([[500, 0, 320], [0, 500, 240], [0, 0, 1]])

        world_point = calibrator.pixel_to_world(pixel_point, depth, camera_matrix)

        assert len(world_point) == 3
        assert world_point[2] == depth

    def test_save_calibration_data(self, calibrator):
        """测试保存标定数据"""
        calibration_data = {
            "camera_matrix": np.eye(3),
            "distortion_coefficients": np.zeros(5),
            "reprojection_error": 0.5
        }

        with patch('builtins.open', create=True) as mock_open, \
             patch('json.dump') as mock_dump:

            success = calibrator.save_calibration_data(calibration_data, "test_calibration.json")

            assert success
            mock_open.assert_called_once()
            mock_dump.assert_called_once()

    def test_load_calibration_data(self, calibrator):
        """测试加载标定数据"""
        expected_data = {
            "camera_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "distortion_coefficients": [0, 0, 0, 0, 0]
        }

        with patch('builtins.open', create=True) as mock_open, \
             patch('json.load', return_value=expected_data) as mock_load:

            data = calibrator.load_calibration_data("test_calibration.json")

            assert data is not None
            assert "camera_matrix" in data
            mock_open.assert_called_once()
            mock_load.assert_called_once()


class TestRobotCalibration:
    """机器人标定测试类"""

    @pytest.fixture
    def calibrator(self):
        """创建机器人标定实例"""
        return RobotCalibration(port="/dev/ttyUSB0", baudrate=115200)

    @pytest.fixture
    def mock_serial(self):
        """模拟串口连接"""
        with patch('serial.Serial') as mock:
            mock.return_value.is_open = True
            mock.return_value.write = Mock()
            mock.return_value.readline = Mock(return_value=b"OK\r\n")
            mock.return_value.close = Mock()
            yield mock

    def test_init(self, calibrator):
        """测试初始化"""
        assert calibrator.port == "/dev/ttyUSB0"
        assert calibrator.baudrate == 115200
        assert not calibrator.is_connected
        assert len(calibrator.dh_parameters) == 6

    @pytest.mark.asyncio
    async def test_connect_success(self, calibrator, mock_serial):
        """测试连接成功"""
        success = await calibrator.connect()

        assert success
        assert calibrator.is_connected

    @pytest.mark.asyncio
    async def test_connect_failure(self, calibrator):
        """测试连接失败"""
        with patch('serial.Serial', side_effect=Exception("连接失败")):
            success = await calibrator.connect()

            assert not success
            assert not calibrator.is_connected

    @pytest.mark.asyncio
    async def test_send_command(self, calibrator, mock_serial):
        """测试发送命令"""
        calibrator.serial_conn = mock_serial.return_value

        response = await calibrator._send_command("TEST")

        assert response == "OK"
        mock_serial.return_value.write.assert_called_once()

    def test_forward_kinematics(self, calibrator):
        """测试正向运动学"""
        joint_angles = [0, 0, 0, 0, 0, 0]  # 全零位置

        position = calibrator.forward_kinematics(joint_angles)

        assert len(position) == 6  # x, y, z, rx, ry, rz
        assert isinstance(position[0], (int, float))

    def test_inverse_kinematics_reachable(self, calibrator):
        """测试逆运动学 - 可达位置"""
        target_pose = [200, 100, 300, 0, 0, 0]

        joint_angles = calibrator.inverse_kinematics(target_pose)

        assert joint_angles is not None
        assert len(joint_angles) == 6

        # 验证正逆运动学一致性
        computed_pose = calibrator.forward_kinematics(joint_angles)
        for i in range(3):  # 只检查位置，不检查姿态
            assert abs(computed_pose[i] - target_pose[i]) < 1.0

    def test_inverse_kinematics_unreachable(self, calibrator):
        """测试逆运动学 - 不可达位置"""
        target_pose = [1000, 1000, 1000, 0, 0, 0]  # 超出工作空间

        joint_angles = calibrator.inverse_kinematics(target_pose)

        assert joint_angles is None

    @pytest.mark.asyncio
    async def test_calibrate_home_position(self, calibrator, mock_serial):
        """测试标定原点位置"""
        calibrator.serial_conn = mock_serial.return_value

        with patch.object(calibrator, '_send_command', return_value="OK"):
            success = await calibrator.calibrate_home_position()

            assert success
            # 检查原点位置是否被记录
            assert hasattr(calibrator, 'home_position')

    @pytest.mark.asyncio
    async def test_calibrate_dh_parameters(self, calibrator):
        """测试DH参数标定"""
        # 模拟测量数据
        sample_positions = [
            ([0, 0, 0, 0, 0, 0], [0, 0, 350, 0, 0, 0]),
            ([90, 0, 0, 0, 0, 0], [0, 350, 0, 0, 0, 90]),
            ([0, 90, 0, 0, 0, 0], [350, 0, 0, 90, 0, 0])
        ]

        with patch.object(calibrator, '_collect_calibration_data', return_value=sample_positions):
            success = await calibrator.calibrate_dh_parameters(num_samples=3)

            assert success
            # 检查DH参数是否被更新
            assert len(calibrator.dh_parameters) == 6

    def test_calculate_transformation_matrix(self, calibrator):
        """测试变换矩阵计算"""
        # DH参数: [a, d, alpha, theta]
        dh_params = [0, 105, np.pi/2, 0]

        T = calibrator._calculate_transformation_matrix(dh_params)

        assert T.shape == (4, 4)
        assert T[3, 3] == 1.0  # 齐次坐标
        assert np.allclose(np.linalg.det(T[:3, :3]), 1.0)  # 旋转矩阵行列式为1

    def test_validate_joint_limits(self, calibrator):
        """测试关节限制验证"""
        # 有效关节角度
        valid_angles = [0, 45, -30, 60, -45, 90]
        assert calibrator._validate_joint_limits(valid_angles)

        # 超出限制的角度
        invalid_angles = [200, 0, 0, 0, 0, 0]
        assert not calibrator._validate_joint_limits(invalid_angles)

    @pytest.mark.asyncio
    async def test_calibrate_hand_eye_success(self, calibrator):
        """测试手眼标定成功"""
        # 模拟标定数据
        calibration_poses = [
            ([100, 100, 200, 0, 0, 0], np.eye(4)),
            ([200, 100, 200, 0, 0, 30], np.eye(4)),
            ([100, 200, 200, 0, 30, 0], np.eye(4))
        ]

        with patch.object(calibrator, '_collect_hand_eye_data', return_value=calibration_poses), \
             patch('cv2.calibrateHandEye') as mock_calibrate:

            mock_calibrate.return_value = (np.eye(3), np.array([0, 0, 0]))

            result = await calibrator.calibrate_hand_eye("camera_calibration.json")

            assert result["success"]
            assert "hand_eye_matrix" in result

    def test_optimize_dh_parameters(self, calibrator):
        """测试DH参数优化"""
        # 准备测试数据
        measured_data = [
            ([0, 0, 0, 0, 0, 0], [0, 0, 350]),
            ([90, 0, 0, 0, 0, 0], [0, 350, 0]),
        ]

        initial_params = calibrator.dh_parameters.copy()

        optimized_params = calibrator._optimize_dh_parameters(measured_data)

        assert len(optimized_params) == 6
        # 参数应该有所变化（除非已经是最优的）
        assert len([p for p in optimized_params if len(p) == 4]) == 6

    def test_calculate_calibration_accuracy(self, calibrator):
        """测试标定精度计算"""
        # 测试数据
        measured_positions = [[100, 100, 200], [200, 100, 200]]
        computed_positions = [[101, 99, 201], [199, 101, 199]]

        accuracy = calibrator._calculate_calibration_accuracy(
            measured_positions, computed_positions
        )

        assert isinstance(accuracy, dict)
        assert "mean_error" in accuracy
        assert "max_error" in accuracy
        assert "std_error" in accuracy

    @pytest.mark.asyncio
    async def test_save_calibration_results(self, calibrator):
        """测试保存标定结果"""
        calibration_results = {
            "dh_parameters": calibrator.dh_parameters,
            "home_position": [0, 0, 350, 0, 0, 0],
            "calibration_accuracy": {"mean_error": 0.5}
        }

        with patch('builtins.open', create=True) as mock_open, \
             patch('json.dump') as mock_dump:

            success = await calibrator.save_calibration_results(
                calibration_results, "robot_calibration.json"
            )

            assert success
            mock_open.assert_called_once()
            mock_dump.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, calibrator, mock_serial):
        """测试断开连接"""
        calibrator.serial_conn = mock_serial.return_value
        calibrator.is_connected = True

        await calibrator.disconnect()

        assert not calibrator.is_connected
        mock_serial.return_value.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
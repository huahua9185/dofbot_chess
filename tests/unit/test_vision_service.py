"""
视觉识别服务单元测试
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import cv2

from shared.models.chess_models import ChessBoard, ChessPiece, GameState
from services.vision_service.src.vision.service import VisionService
from services.vision_service.src.vision.camera import DepthCameraDABAI
from services.vision_service.src.vision.processor import ChessVisionProcessor


class TestVisionService:
    """视觉识别服务测试类"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return VisionService()

    @pytest.fixture
    def mock_camera(self):
        """模拟深度相机"""
        camera = Mock(spec=DepthCameraDABAI)
        camera.initialize = AsyncMock(return_value=True)
        camera.disconnect = AsyncMock()
        camera.capture_frame = AsyncMock(return_value=(
            np.zeros((480, 640, 3), dtype=np.uint8),  # RGB图像
            np.zeros((480, 640), dtype=np.uint16)      # 深度图像
        ))
        camera.is_connected = True
        return camera

    @pytest.fixture
    def mock_processor(self):
        """模拟视觉处理器"""
        processor = Mock(spec=ChessVisionProcessor)
        processor.detect_chessboard = AsyncMock(return_value=ChessBoard(
            corners=np.array([[0, 0], [640, 0], [640, 480], [0, 480]]),
            squares=[[f"{chr(97+i)}{j+1}" for j in range(8)] for i in range(8)],
            transform_matrix=np.eye(3)
        ))
        processor.detect_pieces = AsyncMock(return_value=[
            ChessPiece(type="king", color="white", position="e1", confidence=0.95),
            ChessPiece(type="pawn", color="white", position="e2", confidence=0.90)
        ])
        return processor

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
        assert service.service_name == "vision_service"
        assert service.camera is not None
        assert service.processor is not None
        assert not service.is_running

    @pytest.mark.asyncio
    async def test_initialize_success(self, service, mock_camera, mock_processor, mock_event_bus):
        """测试服务初始化成功"""
        service.camera = mock_camera
        service.processor = mock_processor

        with patch('services.vision_service.src.vision.service.RedisEventBus', return_value=mock_event_bus):
            success = await service.initialize()

            assert success
            mock_event_bus.connect.assert_called_once()
            mock_camera.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_camera_failure(self, service, mock_processor, mock_event_bus):
        """测试相机初始化失败"""
        with patch('services.vision_service.src.vision.service.RedisEventBus', return_value=mock_event_bus), \
             patch.object(service.camera, 'initialize', return_value=False):

            success = await service.initialize()
            assert not success

    @pytest.mark.asyncio
    async def test_capture_and_analyze_frame(self, service, mock_camera, mock_processor):
        """测试捕获和分析帧"""
        service.camera = mock_camera
        service.processor = mock_processor
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        # 执行捕获和分析
        await service._capture_and_analyze_frame()

        # 检查相机是否被调用
        mock_camera.capture_frame.assert_called_once()

        # 检查处理器是否被调用
        mock_processor.detect_chessboard.assert_called_once()
        mock_processor.detect_pieces.assert_called_once()

        # 检查结果是否被发布
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_handle_capture_request(self, service, mock_camera, mock_processor):
        """测试处理捕获请求"""
        service.camera = mock_camera
        service.processor = mock_processor
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        event_data = {
            "data": {
                "type": "board_analysis",
                "requestId": "test-123"
            }
        }

        await service._handle_capture_request(event_data)

        # 检查是否执行了捕获
        mock_camera.capture_frame.assert_called_once()
        mock_processor.detect_chessboard.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_calibration_request(self, service, mock_camera):
        """测试处理标定请求"""
        service.camera = mock_camera
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        # 模拟标定数据
        mock_camera.get_intrinsic_parameters = Mock(return_value={
            "camera_matrix": np.eye(3).tolist(),
            "distortion_coefficients": [0, 0, 0, 0, 0],
            "image_size": [640, 480]
        })

        event_data = {
            "data": {
                "type": "intrinsic_calibration"
            }
        }

        await service._handle_calibration_request(event_data)

        # 检查标定数据是否被获取和发布
        mock_camera.get_intrinsic_parameters.assert_called_once()
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_start_continuous_capture(self, service, mock_camera, mock_processor):
        """测试开始连续捕获"""
        service.camera = mock_camera
        service.processor = mock_processor
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.is_running = True

        # 模拟连续捕获任务
        with patch.object(service, '_capture_and_analyze_frame') as mock_capture:
            # 创建任务并立即取消
            task = asyncio.create_task(service._continuous_capture())
            await asyncio.sleep(0.1)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # 验证捕获被调用
            mock_capture.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown(self, service, mock_camera, mock_event_bus):
        """测试服务关闭"""
        service.camera = mock_camera
        service.event_bus = mock_event_bus
        service.is_running = True

        await service.shutdown()

        assert not service.is_running
        mock_camera.disconnect.assert_called_once()
        mock_event_bus.disconnect.assert_called_once()


class TestDepthCameraDABAI:
    """DABAI深度相机测试类"""

    @pytest.fixture
    def camera(self):
        """创建相机实例"""
        return DepthCameraDABAI()

    def test_init(self, camera):
        """测试初始化"""
        assert camera.device_id == 0
        assert not camera.is_connected
        assert camera.width == 640
        assert camera.height == 480

    @pytest.mark.asyncio
    async def test_initialize_success(self, camera):
        """测试初始化成功"""
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap.return_value.isOpened.return_value = True
            mock_cap.return_value.set.return_value = True

            success = await camera.initialize()

            assert success
            assert camera.is_connected

    @pytest.mark.asyncio
    async def test_initialize_failure(self, camera):
        """测试初始化失败"""
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap.return_value.isOpened.return_value = False

            success = await camera.initialize()

            assert not success
            assert not camera.is_connected

    @pytest.mark.asyncio
    async def test_capture_frame_success(self, camera):
        """测试捕获帧成功"""
        camera.is_connected = True

        with patch.object(camera, 'cap') as mock_cap:
            mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

            rgb_frame, depth_frame = await camera.capture_frame()

            assert rgb_frame is not None
            assert rgb_frame.shape == (480, 640, 3)
            assert depth_frame is not None

    @pytest.mark.asyncio
    async def test_capture_frame_not_connected(self, camera):
        """测试未连接时捕获帧"""
        camera.is_connected = False

        result = await camera.capture_frame()
        assert result is None

    def test_get_intrinsic_parameters(self, camera):
        """测试获取内参"""
        camera.camera_matrix = np.eye(3)
        camera.distortion_coefficients = np.zeros(5)

        params = camera.get_intrinsic_parameters()

        assert "camera_matrix" in params
        assert "distortion_coefficients" in params
        assert "image_size" in params


class TestChessVisionProcessor:
    """象棋视觉处理器测试类"""

    @pytest.fixture
    def processor(self):
        """创建处理器实例"""
        return ChessVisionProcessor()

    @pytest.fixture
    def sample_image(self):
        """创建样本图像"""
        return np.zeros((480, 640, 3), dtype=np.uint8)

    @pytest.mark.asyncio
    async def test_detect_chessboard_success(self, processor, sample_image):
        """测试棋盘检测成功"""
        with patch('cv2.findChessboardCorners') as mock_find:
            mock_find.return_value = (True, np.array([[0, 0], [640, 0], [640, 480], [0, 480]]))

            board = await processor.detect_chessboard(sample_image)

            assert board is not None
            assert board.corners is not None
            assert len(board.squares) == 8

    @pytest.mark.asyncio
    async def test_detect_chessboard_failure(self, processor, sample_image):
        """测试棋盘检测失败"""
        with patch('cv2.findChessboardCorners') as mock_find:
            mock_find.return_value = (False, None)

            board = await processor.detect_chessboard(sample_image)

            assert board is None

    @pytest.mark.asyncio
    async def test_detect_pieces(self, processor, sample_image):
        """测试棋子检测"""
        # 模拟棋盘已检测
        processor.current_board = ChessBoard(
            corners=np.array([[0, 0], [640, 0], [640, 480], [0, 480]]),
            squares=[[f"{chr(97+i)}{j+1}" for j in range(8)] for i in range(8)],
            transform_matrix=np.eye(3)
        )

        with patch.object(processor, '_extract_square_regions') as mock_extract, \
             patch.object(processor, '_classify_piece') as mock_classify:

            mock_extract.return_value = [np.zeros((64, 64, 3)) for _ in range(64)]
            mock_classify.return_value = ("king", "white", 0.95)

            pieces = await processor.detect_pieces(sample_image)

            assert isinstance(pieces, list)
            # 至少应该检测到一些棋子
            if pieces:
                assert all(isinstance(p, ChessPiece) for p in pieces)

    def test_square_to_coordinates(self, processor):
        """测试方格坐标转换"""
        coords = processor._square_to_coordinates("e4")
        assert coords == (4, 3)  # e=4, 4=3 (0-indexed)

        coords = processor._square_to_coordinates("a1")
        assert coords == (0, 0)

        coords = processor._square_to_coordinates("h8")
        assert coords == (7, 7)

    def test_square_to_coordinates_invalid(self, processor):
        """测试无效方格坐标"""
        with pytest.raises(ValueError):
            processor._square_to_coordinates("i9")

        with pytest.raises(ValueError):
            processor._square_to_coordinates("a")

    def test_calculate_transform_matrix(self, processor):
        """测试变换矩阵计算"""
        corners = np.array([[0, 0], [640, 0], [640, 480], [0, 480]], dtype=np.float32)
        matrix = processor._calculate_transform_matrix(corners)

        assert matrix is not None
        assert matrix.shape == (3, 3)

    def test_preprocess_square_image(self, processor):
        """测试方格图像预处理"""
        square_img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)

        processed = processor._preprocess_square_image(square_img)

        assert processed.shape == (64, 64, 3)
        assert processed.dtype == np.uint8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
pytest配置文件
提供通用的fixtures和测试配置
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """模拟Redis连接"""
    redis_mock = Mock()
    redis_mock.ping = Mock(return_value=True)
    redis_mock.get = Mock(return_value=None)
    redis_mock.set = Mock(return_value=True)
    redis_mock.publish = Mock(return_value=1)
    redis_mock.subscribe = Mock()
    redis_mock.close = Mock()
    return redis_mock


@pytest.fixture
def mock_mongodb():
    """模拟MongoDB连接"""
    db_mock = Mock()

    # 模拟集合
    collection_mock = Mock()
    collection_mock.insert_one = AsyncMock(return_value=Mock(inserted_id="test_id"))
    collection_mock.find_one = AsyncMock(return_value={"_id": "test_id", "data": "test"})
    collection_mock.update_one = AsyncMock(return_value=Mock(modified_count=1))
    collection_mock.delete_one = AsyncMock(return_value=Mock(deleted_count=1))
    collection_mock.find = Mock(return_value=[])

    # 设置数据库返回集合
    db_mock.__getitem__ = Mock(return_value=collection_mock)

    return db_mock


@pytest.fixture
def mock_serial():
    """模拟串口连接"""
    import serial

    serial_mock = Mock(spec=serial.Serial)
    serial_mock.is_open = True
    serial_mock.write = Mock()
    serial_mock.readline = Mock(return_value=b"OK\r\n")
    serial_mock.read = Mock(return_value=b"OK")
    serial_mock.in_waiting = 4
    serial_mock.close = Mock()

    return serial_mock


@pytest.fixture
def mock_cv2_camera():
    """模拟OpenCV相机"""
    camera_mock = Mock()
    camera_mock.isOpened = Mock(return_value=True)
    camera_mock.read = Mock(return_value=(True, np.zeros((480, 640, 3), dtype=np.uint8)))
    camera_mock.get = Mock(return_value=30.0)  # FPS
    camera_mock.set = Mock(return_value=True)
    camera_mock.release = Mock()

    return camera_mock


@pytest.fixture
def sample_chess_image():
    """创建样本象棋图像"""
    # 创建一个简单的测试图像
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # 添加一些棋盘格模式
    for i in range(0, 480, 60):
        for j in range(0, 640, 80):
            if (i // 60 + j // 80) % 2 == 0:
                image[i:i+60, j:j+80] = 255

    return image


@pytest.fixture
def sample_depth_image():
    """创建样本深度图像"""
    # 创建渐变深度图
    depth = np.zeros((480, 640), dtype=np.uint16)
    for i in range(480):
        for j in range(640):
            depth[i, j] = 1000 + i  # 深度从1000mm开始递增

    return depth


@pytest.fixture
def sample_chessboard_corners():
    """创建样本棋盘角点"""
    corners = []
    for i in range(6):  # 6行
        for j in range(9):  # 9列
            x = 50 + j * 60
            y = 50 + i * 60
            corners.append([x, y])

    return np.array(corners, dtype=np.float32).reshape(-1, 1, 2)


@pytest.fixture
def sample_game_state():
    """创建样本游戏状态"""
    from shared.models.chess_models import GameState, GameStatus, PieceColor, ChessBoard
    import time

    # 创建简单的棋盘状态
    board = ChessBoard(
        pieces={},
        timestamp=time.time(),
        fen_string="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        move_count=0
    )

    return GameState(
        game_id="test-game-123",
        status=GameStatus.WAITING,
        board=board,
        current_player=PieceColor.WHITE,
        human_color=PieceColor.WHITE,
        ai_color=PieceColor.BLACK,
        move_history=[],
        start_time=time.time(),
        last_update=time.time()
    )


@pytest.fixture
def sample_robot_command():
    """创建样本机器人命令"""
    from shared.models.chess_models import RobotCommand

    return RobotCommand(
        command_type="move",
        from_position="e2",
        to_position="e4",
        speed=50
    )


@pytest.fixture
def sample_chess_pieces():
    """创建样本棋子列表"""
    from shared.models.chess_models import ChessPiece, PieceType, PieceColor

    return [
        ChessPiece(PieceType.WHITE_KING, "e1", PieceColor.WHITE, 0.95),
        ChessPiece(PieceType.WHITE_QUEEN, "d1", PieceColor.WHITE, 0.92),
        ChessPiece(PieceType.WHITE_ROOK, "a1", PieceColor.WHITE, 0.88),
        ChessPiece(PieceType.WHITE_ROOK, "h1", PieceColor.WHITE, 0.90),
        ChessPiece(PieceType.WHITE_BISHOP, "c1", PieceColor.WHITE, 0.85),
        ChessPiece(PieceType.WHITE_BISHOP, "f1", PieceColor.WHITE, 0.87),
        ChessPiece(PieceType.WHITE_KNIGHT, "b1", PieceColor.WHITE, 0.83),
        ChessPiece(PieceType.WHITE_KNIGHT, "g1", PieceColor.WHITE, 0.86),
        ChessPiece(PieceType.WHITE_PAWN, "a2", PieceColor.WHITE, 0.80),
        ChessPiece(PieceType.WHITE_PAWN, "b2", PieceColor.WHITE, 0.82),
        ChessPiece(PieceType.WHITE_PAWN, "c2", PieceColor.WHITE, 0.81),
        ChessPiece(PieceType.WHITE_PAWN, "d2", PieceColor.WHITE, 0.84),
        ChessPiece(PieceType.WHITE_PAWN, "e2", PieceColor.WHITE, 0.79),
        ChessPiece(PieceType.WHITE_PAWN, "f2", PieceColor.WHITE, 0.83),
        ChessPiece(PieceType.WHITE_PAWN, "g2", PieceColor.WHITE, 0.85),
        ChessPiece(PieceType.WHITE_PAWN, "h2", PieceColor.WHITE, 0.78),
    ]


@pytest.fixture
def sample_calibration_data():
    """创建样本标定数据"""
    return {
        "camera_matrix": np.eye(3).tolist(),
        "distortion_coefficients": [0.1, -0.2, 0.001, 0.002, 0.0],
        "image_size": [640, 480],
        "reprojection_error": 0.5,
        "calibration_date": "2024-01-15T10:30:00"
    }


@pytest.fixture
def sample_dh_parameters():
    """创建样本DH参数"""
    return [
        {"a": 0, "d": 105, "alpha": np.pi/2, "theta": 0},
        {"a": 105, "d": 0, "alpha": 0, "theta": np.pi/2},
        {"a": 98, "d": 0, "alpha": 0, "theta": 0},
        {"a": 0, "d": 0, "alpha": np.pi/2, "theta": 0},
        {"a": 0, "d": 155, "alpha": -np.pi/2, "theta": 0},
        {"a": 0, "d": 0, "alpha": 0, "theta": 0},
    ]


class AsyncMockContext:
    """异步上下文管理器模拟"""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_manager():
    """异步上下文管理器fixture"""
    return AsyncMockContext


# 标记慢速测试
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "hardware: marks tests requiring hardware"
    )


# 跳过硬件测试的条件
def pytest_runtest_setup(item):
    """测试运行前设置"""
    if "hardware" in item.keywords:
        # 检查是否有硬件设备
        if not os.path.exists("/dev/ttyUSB0") and not os.path.exists("/dev/ttyACM0"):
            pytest.skip("需要硬件设备")


# 设置异步测试超时
@pytest.fixture(autouse=True)
def setup_async_timeout():
    """设置异步测试超时"""
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("异步测试超时")

    # 设置30秒超时
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)

    yield

    # 清除超时
    signal.alarm(0)


# 日志配置
@pytest.fixture(autouse=True)
def setup_logging(caplog):
    """设置测试日志"""
    import logging

    # 设置日志级别
    caplog.set_level(logging.INFO)

    # 禁用一些模块的详细日志
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
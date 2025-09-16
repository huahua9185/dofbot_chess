"""
核心功能单元测试
测试系统关键组件的基础功能
"""
import pytest
import sys
import os
import time
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.models.chess_models import (
    ChessPiece, ChessBoard, ChessMove, GameState,
    PieceType, PieceColor, GameStatus, Position3D, Position6D,
    VisionDetection, RobotCommand, RobotStatus, SystemMetrics
)


class TestChessPieceModel:
    """测试棋子数据模型"""

    def test_chess_piece_creation(self):
        """测试棋子创建"""
        piece = ChessPiece(
            piece_type=PieceType.WHITE_KING,
            position="e1",
            color=PieceColor.WHITE,
            confidence=0.95
        )

        assert piece.piece_type == PieceType.WHITE_KING
        assert piece.position == "e1"
        assert piece.color == PieceColor.WHITE
        assert piece.confidence == 0.95

    def test_chess_board_creation(self):
        """测试棋盘创建"""
        timestamp = time.time()
        board = ChessBoard(
            pieces={},
            timestamp=timestamp,
            fen_string="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move_count=0
        )

        assert isinstance(board.pieces, dict)
        assert board.timestamp == timestamp
        assert "rnbqkbnr" in board.fen_string
        assert board.move_count == 0

    def test_chess_move_creation(self):
        """测试象棋移动"""
        move = ChessMove(
            from_square="e2",
            to_square="e4",
            piece=PieceType.WHITE_PAWN,
            notation="e4"
        )

        assert move.from_square == "e2"
        assert move.to_square == "e4"
        assert move.piece == PieceType.WHITE_PAWN
        assert move.notation == "e4"
        assert not move.is_castling
        assert not move.is_en_passant


class TestGameState:
    """测试游戏状态管理"""

    def test_game_state_creation(self):
        """测试游戏状态创建"""
        board = ChessBoard(
            pieces={},
            timestamp=time.time(),
            fen_string="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move_count=0
        )

        game_state = GameState(
            game_id="test-game-456",
            status=GameStatus.WAITING,
            board=board,
            current_player=PieceColor.WHITE,
            human_color=PieceColor.WHITE,
            ai_color=PieceColor.BLACK,
            move_history=[],
            start_time=time.time(),
            last_update=time.time()
        )

        assert game_state.game_id == "test-game-456"
        assert game_state.status == GameStatus.WAITING
        assert game_state.current_player == PieceColor.WHITE
        assert game_state.human_color == PieceColor.WHITE
        assert game_state.ai_color == PieceColor.BLACK
        assert len(game_state.move_history) == 0


class TestVisionDetection:
    """测试视觉检测模型"""

    def test_vision_detection_creation(self):
        """测试视觉检测结果创建"""
        board = ChessBoard(
            pieces={},
            timestamp=time.time(),
            fen_string="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move_count=0
        )

        detection = VisionDetection(
            board_state=board,
            detected_move=None,
            detection_confidence=0.92,
            processing_time=0.15,
            image_timestamp=time.time(),
            camera_id="dabai_dc_w2"
        )

        assert detection.board_state == board
        assert detection.detected_move is None
        assert detection.detection_confidence == 0.92
        assert detection.processing_time == 0.15
        assert detection.camera_id == "dabai_dc_w2"


class TestRobotModels:
    """测试机器人相关模型"""

    def test_robot_command_creation(self):
        """测试机器人命令创建"""
        command = RobotCommand(
            command_type="move",
            from_position="e2",
            to_position="e4",
            speed=75,
            precision=0.5,
            timeout=25.0
        )

        assert command.command_type == "move"
        assert command.from_position == "e2"
        assert command.to_position == "e4"
        assert command.speed == 75
        assert command.precision == 0.5
        assert command.timeout == 25.0

    def test_robot_status_creation(self):
        """测试机器人状态创建"""
        position = Position6D(x=200, y=100, z=300, rx=0, ry=0, rz=0)

        status = RobotStatus(
            is_connected=True,
            is_moving=False,
            current_position=position,
            joint_angles=[0, 45, -30, 0, 75, 0],
            gripper_state=False
        )

        assert status.is_connected
        assert not status.is_moving
        assert status.current_position.x == 200
        assert len(status.joint_angles) == 6
        assert status.joint_angles[1] == 45
        assert not status.gripper_state
        assert status.last_update > 0


class TestSystemMetrics:
    """测试系统性能指标"""

    def test_system_metrics_creation(self):
        """测试系统指标创建"""
        metrics = SystemMetrics(
            cpu_usage=45.5,
            memory_usage=62.3,
            disk_usage=78.1,
            gpu_usage=23.4,
            temperature=68.5,
            vision_fps=15.2,
            detection_latency=0.08,
            robot_response_time=1.2,
            ai_thinking_time=3.5
        )

        assert metrics.cpu_usage == 45.5
        assert metrics.memory_usage == 62.3
        assert metrics.disk_usage == 78.1
        assert metrics.gpu_usage == 23.4
        assert metrics.temperature == 68.5
        assert metrics.vision_fps == 15.2
        assert metrics.detection_latency == 0.08
        assert metrics.robot_response_time == 1.2
        assert metrics.ai_thinking_time == 3.5
        assert metrics.timestamp > 0


class TestPositionModels:
    """测试位置和姿态模型"""

    def test_position_3d_operations(self):
        """测试3D位置操作"""
        pos1 = Position3D(x=10, y=20, z=30)
        pos2 = Position3D(x=15, y=25, z=35)

        # 测试基本属性
        assert pos1.x == 10
        assert pos1.y == 20
        assert pos1.z == 30

        # 测试不同位置
        assert pos1.x != pos2.x
        assert pos1.y != pos2.y
        assert pos1.z != pos2.z

    def test_position_6d_operations(self):
        """测试6D位姿操作"""
        pose = Position6D(x=100, y=200, z=300, rx=10, ry=20, rz=30)

        # 测试位置分量
        assert pose.x == 100
        assert pose.y == 200
        assert pose.z == 300

        # 测试姿态分量
        assert pose.rx == 10
        assert pose.ry == 20
        assert pose.rz == 30


class TestDataValidation:
    """测试数据验证功能"""

    def test_piece_color_validation(self):
        """测试棋子颜色验证"""
        from shared.models.chess_models import get_piece_color

        # 测试白棋
        assert get_piece_color(PieceType.WHITE_KING) == PieceColor.WHITE
        assert get_piece_color(PieceType.WHITE_PAWN) == PieceColor.WHITE

        # 测试黑棋
        assert get_piece_color(PieceType.BLACK_QUEEN) == PieceColor.BLACK
        assert get_piece_color(PieceType.BLACK_ROOK) == PieceColor.BLACK

        # 测试空位
        assert get_piece_color(PieceType.EMPTY) is None

    def test_square_validation(self):
        """测试方格验证"""
        from shared.models.chess_models import is_valid_square

        # 测试有效方格
        valid_squares = ["a1", "e4", "h8", "d5", "b2", "f7"]
        for square in valid_squares:
            assert is_valid_square(square), f"方格 {square} 应该是有效的"

        # 测试无效方格
        invalid_squares = ["i9", "a0", "z5", "e9", "j1", "a10"]
        for square in invalid_squares:
            assert not is_valid_square(square), f"方格 {square} 应该是无效的"

    def test_coordinate_conversion_consistency(self):
        """测试坐标转换一致性"""
        from shared.models.chess_models import square_to_coords, coords_to_square

        # 测试所有有效方格的转换一致性
        for col in range(8):
            for row in range(8):
                # 坐标 -> 方格 -> 坐标
                square = coords_to_square(col, row)
                converted_col, converted_row = square_to_coords(square)

                assert col == converted_col, f"列坐标不一致: {col} != {converted_col}"
                assert row == converted_row, f"行坐标不一致: {row} != {converted_row}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
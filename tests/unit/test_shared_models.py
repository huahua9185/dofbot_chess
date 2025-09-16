"""
共享模型单元测试
"""
import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock

from shared.models.chess_models import (
    Position3D, Position6D, ChessPiece, ChessBoard,
    GameState, Player, MoveResult, RobotCommand, RobotStatus,
    GameEvent, CalibrationResult
)


class TestPosition3D:
    """3D位置模型测试"""

    def test_init(self):
        """测试初始化"""
        pos = Position3D(10.0, 20.0, 30.0)

        assert pos.x == 10.0
        assert pos.y == 20.0
        assert pos.z == 30.0

    def test_from_dict(self):
        """测试从字典创建"""
        data = {"x": 1.0, "y": 2.0, "z": 3.0}
        pos = Position3D.from_dict(data)

        assert pos.x == 1.0
        assert pos.y == 2.0
        assert pos.z == 3.0

    def test_to_dict(self):
        """测试转换为字典"""
        pos = Position3D(5.0, 10.0, 15.0)
        data = pos.to_dict()

        expected = {"x": 5.0, "y": 10.0, "z": 15.0}
        assert data == expected

    def test_distance_to(self):
        """测试计算距离"""
        pos1 = Position3D(0.0, 0.0, 0.0)
        pos2 = Position3D(3.0, 4.0, 0.0)

        distance = pos1.distance_to(pos2)
        assert abs(distance - 5.0) < 0.001

    def test_add(self):
        """测试位置相加"""
        pos1 = Position3D(1.0, 2.0, 3.0)
        pos2 = Position3D(4.0, 5.0, 6.0)

        result = pos1 + pos2
        assert result.x == 5.0
        assert result.y == 7.0
        assert result.z == 9.0

    def test_subtract(self):
        """测试位置相减"""
        pos1 = Position3D(10.0, 8.0, 6.0)
        pos2 = Position3D(4.0, 3.0, 2.0)

        result = pos1 - pos2
        assert result.x == 6.0
        assert result.y == 5.0
        assert result.z == 4.0

    def test_equality(self):
        """测试相等性"""
        pos1 = Position3D(1.0, 2.0, 3.0)
        pos2 = Position3D(1.0, 2.0, 3.0)
        pos3 = Position3D(1.0, 2.0, 4.0)

        assert pos1 == pos2
        assert pos1 != pos3


class TestPosition6D:
    """6D位置模型测试"""

    def test_init(self):
        """测试初始化"""
        pos = Position6D(1.0, 2.0, 3.0, 0.1, 0.2, 0.3)

        assert pos.x == 1.0
        assert pos.y == 2.0
        assert pos.z == 3.0
        assert pos.rx == 0.1
        assert pos.ry == 0.2
        assert pos.rz == 0.3

    def test_to_matrix(self):
        """测试转换为变换矩阵"""
        pos = Position6D(10.0, 20.0, 30.0, 0.0, 0.0, np.pi/2)
        matrix = pos.to_matrix()

        assert matrix.shape == (4, 4)
        assert matrix[3, 3] == 1.0
        assert abs(matrix[0, 3] - 10.0) < 0.001
        assert abs(matrix[1, 3] - 20.0) < 0.001
        assert abs(matrix[2, 3] - 30.0) < 0.001

    def test_from_matrix(self):
        """测试从变换矩阵创建"""
        # 创建单位变换矩阵，只有平移
        matrix = np.eye(4)
        matrix[0:3, 3] = [5.0, 10.0, 15.0]

        pos = Position6D.from_matrix(matrix)

        assert abs(pos.x - 5.0) < 0.001
        assert abs(pos.y - 10.0) < 0.001
        assert abs(pos.z - 15.0) < 0.001

    def test_get_position3d(self):
        """测试获取3D位置"""
        pos6d = Position6D(1.0, 2.0, 3.0, 0.1, 0.2, 0.3)
        pos3d = pos6d.get_position3d()

        assert pos3d.x == 1.0
        assert pos3d.y == 2.0
        assert pos3d.z == 3.0


class TestChessPiece:
    """棋子模型测试"""

    def test_init(self):
        """测试初始化"""
        piece = ChessPiece(
            type="king",
            color="white",
            position="e1",
            confidence=0.95
        )

        assert piece.type == "king"
        assert piece.color == "white"
        assert piece.position == "e1"
        assert piece.confidence == 0.95

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "type": "pawn",
            "color": "black",
            "position": "e7",
            "confidence": 0.88
        }

        piece = ChessPiece.from_dict(data)

        assert piece.type == "pawn"
        assert piece.color == "black"
        assert piece.position == "e7"
        assert piece.confidence == 0.88

    def test_to_dict(self):
        """测试转换为字典"""
        piece = ChessPiece("queen", "white", "d1", 0.92)
        data = piece.to_dict()

        expected = {
            "type": "queen",
            "color": "white",
            "position": "d1",
            "confidence": 0.92
        }
        assert data == expected

    def test_is_valid_type(self):
        """测试棋子类型验证"""
        assert ChessPiece.is_valid_type("king")
        assert ChessPiece.is_valid_type("pawn")
        assert not ChessPiece.is_valid_type("invalid")

    def test_is_valid_color(self):
        """测试颜色验证"""
        assert ChessPiece.is_valid_color("white")
        assert ChessPiece.is_valid_color("black")
        assert not ChessPiece.is_valid_color("red")

    def test_is_valid_position(self):
        """测试位置验证"""
        assert ChessPiece.is_valid_position("e4")
        assert ChessPiece.is_valid_position("a1")
        assert ChessPiece.is_valid_position("h8")
        assert not ChessPiece.is_valid_position("i9")
        assert not ChessPiece.is_valid_position("e")


class TestChessBoard:
    """棋盘模型测试"""

    def test_init(self):
        """测试初始化"""
        corners = np.array([[0, 0], [640, 0], [640, 480], [0, 480]])
        squares = [[f"{chr(97+i)}{j+1}" for j in range(8)] for i in range(8)]
        transform_matrix = np.eye(3)

        board = ChessBoard(corners, squares, transform_matrix)

        assert board.corners.shape == (4, 2)
        assert len(board.squares) == 8
        assert len(board.squares[0]) == 8
        assert board.transform_matrix.shape == (3, 3)

    def test_get_square_corners(self):
        """测试获取方格角点"""
        corners = np.array([[0, 0], [640, 0], [640, 480], [0, 480]])
        squares = [[f"{chr(97+i)}{j+1}" for j in range(8)] for i in range(8)]
        transform_matrix = np.eye(3)

        board = ChessBoard(corners, squares, transform_matrix)

        square_corners = board.get_square_corners("e4")
        assert square_corners is not None
        assert len(square_corners) == 4

    def test_pixel_to_square(self):
        """测试像素到方格转换"""
        corners = np.array([[0, 0], [640, 0], [640, 480], [0, 480]])
        squares = [[f"{chr(97+i)}{j+1}" for j in range(8)] for i in range(8)]
        transform_matrix = np.eye(3)

        board = ChessBoard(corners, squares, transform_matrix)

        # 测试中心点
        square = board.pixel_to_square(320, 240)
        assert square in [f"{chr(97+i)}{j+1}" for i in range(8) for j in range(8)]

    def test_is_valid(self):
        """测试棋盘有效性"""
        corners = np.array([[0, 0], [640, 0], [640, 480], [0, 480]])
        squares = [[f"{chr(97+i)}{j+1}" for j in range(8)] for i in range(8)]
        transform_matrix = np.eye(3)

        board = ChessBoard(corners, squares, transform_matrix)
        assert board.is_valid()

        # 测试无效棋盘
        invalid_corners = np.array([[0, 0], [0, 0], [0, 0], [0, 0]])
        invalid_board = ChessBoard(invalid_corners, squares, transform_matrix)
        assert not invalid_board.is_valid()


class TestGameState:
    """游戏状态模型测试"""

    def test_init(self):
        """测试初始化"""
        white_player = Player("human", "Alice")
        black_player = Player("ai", "Stockfish")

        state = GameState(
            game_id="game-123",
            white_player=white_player,
            black_player=black_player
        )

        assert state.game_id == "game-123"
        assert state.status == "waiting"
        assert state.current_player == "white"
        assert state.move_count == 0

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "game_id": "game-456",
            "white_player": {"type": "human", "name": "Bob"},
            "black_player": {"type": "ai", "name": "Stockfish"},
            "status": "playing",
            "current_player": "black",
            "move_count": 5
        }

        state = GameState.from_dict(data)

        assert state.game_id == "game-456"
        assert state.status == "playing"
        assert state.current_player == "black"
        assert state.move_count == 5

    def test_make_move(self):
        """测试执行移动"""
        state = GameState("game-123", Player("human", "Alice"), Player("ai", "Bot"))

        state.make_move("e2", "e4", "pawn")

        assert state.move_count == 1
        assert state.current_player == "black"
        assert len(state.move_history) == 1

    def test_is_valid_move(self):
        """测试移动有效性验证"""
        state = GameState("game-123", Player("human", "Alice"), Player("ai", "Bot"))

        # 测试有效移动（需要模拟棋局逻辑）
        with patch('chess.Board') as mock_board:
            mock_board.return_value.is_legal.return_value = True
            assert state.is_valid_move("e2", "e4")

        # 测试无效移动
        with patch('chess.Board') as mock_board:
            mock_board.return_value.is_legal.return_value = False
            assert not state.is_valid_move("e2", "e5")

    def test_is_game_over(self):
        """测试游戏结束检测"""
        state = GameState("game-123", Player("human", "Alice"), Player("ai", "Bot"))

        # 游戏进行中
        with patch('chess.Board') as mock_board:
            mock_board.return_value.is_game_over.return_value = False
            assert not state.is_game_over()

        # 游戏结束
        with patch('chess.Board') as mock_board:
            mock_board.return_value.is_game_over.return_value = True
            assert state.is_game_over()


class TestMoveResult:
    """移动结果模型测试"""

    def test_init_success(self):
        """测试成功移动初始化"""
        result = MoveResult(
            success=True,
            move="e2e4",
            new_fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        )

        assert result.success is True
        assert result.move == "e2e4"
        assert result.error is None

    def test_init_failure(self):
        """测试失败移动初始化"""
        result = MoveResult(
            success=False,
            error="Invalid move"
        )

        assert result.success is False
        assert result.move is None
        assert result.error == "Invalid move"

    def test_to_dict(self):
        """测试转换为字典"""
        result = MoveResult(
            success=True,
            move="e2e4",
            new_fen="new_position",
            is_checkmate=False,
            is_stalemate=False
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["move"] == "e2e4"
        assert data["is_checkmate"] is False


class TestRobotCommand:
    """机器人命令模型测试"""

    def test_init(self):
        """测试初始化"""
        command = RobotCommand(
            command_type="move",
            from_position="e2",
            to_position="e4",
            speed=50
        )

        assert command.command_type == "move"
        assert command.from_position == "e2"
        assert command.to_position == "e4"
        assert command.speed == 50

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "command_type": "pick",
            "from_position": "e4",
            "speed": 30
        }

        command = RobotCommand.from_dict(data)

        assert command.command_type == "pick"
        assert command.from_position == "e4"
        assert command.speed == 30

    def test_is_valid(self):
        """测试命令有效性"""
        # 有效的移动命令
        valid_move = RobotCommand("move", from_position="e2", to_position="e4")
        assert valid_move.is_valid()

        # 无效的移动命令（缺少目标位置）
        invalid_move = RobotCommand("move", from_position="e2")
        assert not invalid_move.is_valid()

        # 有效的回原点命令
        valid_home = RobotCommand("home")
        assert valid_home.is_valid()


class TestRobotStatus:
    """机器人状态模型测试"""

    def test_init(self):
        """测试初始化"""
        position = Position6D(100, 200, 300, 0, 0, 0)

        status = RobotStatus(
            is_connected=True,
            is_moving=False,
            current_position=position,
            joint_angles=[0, 30, -30, 0, 60, 0],
            gripper_state=True
        )

        assert status.is_connected is True
        assert status.is_moving is False
        assert status.current_position == position
        assert len(status.joint_angles) == 6
        assert status.gripper_state is True

    def test_to_dict(self):
        """测试转换为字典"""
        position = Position6D(10, 20, 30, 0, 0, 0)

        status = RobotStatus(
            is_connected=True,
            is_moving=True,
            current_position=position,
            joint_angles=[10, 20, 30, 40, 50, 60],
            gripper_state=False
        )

        data = status.to_dict()

        assert data["is_connected"] is True
        assert data["is_moving"] is True
        assert "current_position" in data
        assert len(data["joint_angles"]) == 6


class TestGameEvent:
    """游戏事件模型测试"""

    def test_init(self):
        """测试初始化"""
        event = GameEvent(
            event_type="move_made",
            game_id="game-123",
            source="player",
            data={"move": "e2e4"}
        )

        assert event.event_type == "move_made"
        assert event.game_id == "game-123"
        assert event.source == "player"
        assert event.data["move"] == "e2e4"
        assert isinstance(event.timestamp, datetime)

    def test_from_dict(self):
        """测试从字典创建"""
        now = datetime.now()
        data = {
            "event_type": "game_started",
            "game_id": "game-456",
            "source": "game_manager",
            "data": {"players": ["Alice", "Bob"]},
            "timestamp": now.isoformat()
        }

        event = GameEvent.from_dict(data)

        assert event.event_type == "game_started"
        assert event.game_id == "game-456"
        assert event.source == "game_manager"

    def test_to_dict(self):
        """测试转换为字典"""
        event = GameEvent(
            event_type="game_ended",
            game_id="game-789",
            source="game_manager",
            data={"result": "white_wins"}
        )

        data = event.to_dict()

        assert data["event_type"] == "game_ended"
        assert data["game_id"] == "game-789"
        assert "timestamp" in data


class TestCalibrationResult:
    """标定结果模型测试"""

    def test_init(self):
        """测试初始化"""
        result = CalibrationResult(
            calibration_type="camera",
            success=True,
            parameters={
                "camera_matrix": [[500, 0, 320], [0, 500, 240], [0, 0, 1]],
                "distortion_coefficients": [0.1, -0.2, 0.001, 0.002, 0.1]
            },
            error=0.5
        )

        assert result.calibration_type == "camera"
        assert result.success is True
        assert "camera_matrix" in result.parameters
        assert result.error == 0.5

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "calibration_type": "robot",
            "success": True,
            "parameters": {
                "dh_parameters": [[0, 105, 1.57, 0]]
            },
            "error": 1.2
        }

        result = CalibrationResult.from_dict(data)

        assert result.calibration_type == "robot"
        assert result.success is True
        assert "dh_parameters" in result.parameters

    def test_is_valid(self):
        """测试结果有效性"""
        # 有效结果
        valid_result = CalibrationResult(
            calibration_type="camera",
            success=True,
            parameters={"test": "value"}
        )
        assert valid_result.is_valid()

        # 无效结果（成功但无参数）
        invalid_result = CalibrationResult(
            calibration_type="camera",
            success=True,
            parameters={}
        )
        assert not invalid_result.is_valid()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
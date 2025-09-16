"""
基础单元测试
"""
import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.models.chess_models import (
    PieceType, PieceColor, GameStatus, Position3D, Position6D,
    square_to_coords, coords_to_square, get_piece_color, is_valid_square
)


class TestBasicFunctionality:
    """基础功能测试"""

    def test_piece_types(self):
        """测试棋子类型"""
        assert PieceType.WHITE_KING.value == "white_king"
        assert PieceType.BLACK_QUEEN.value == "black_queen"
        assert PieceType.EMPTY.value == "empty"

    def test_piece_colors(self):
        """测试棋子颜色"""
        assert PieceColor.WHITE.value == "white"
        assert PieceColor.BLACK.value == "black"

    def test_game_status(self):
        """测试游戏状态"""
        assert GameStatus.WAITING.value == "waiting"
        assert GameStatus.PLAYING.value == "playing"
        assert GameStatus.FINISHED.value == "finished"

    def test_position_3d(self):
        """测试3D位置"""
        pos = Position3D(x=10.0, y=20.0, z=30.0)
        assert pos.x == 10.0
        assert pos.y == 20.0
        assert pos.z == 30.0

    def test_position_6d(self):
        """测试6D位姿"""
        pos = Position6D(x=10.0, y=20.0, z=30.0, rx=1.0, ry=2.0, rz=3.0)
        assert pos.x == 10.0
        assert pos.z == 30.0
        assert pos.rx == 1.0
        assert pos.rz == 3.0

    def test_square_to_coords(self):
        """测试方格坐标转换"""
        assert square_to_coords("a1") == (0, 0)
        assert square_to_coords("e4") == (4, 3)
        assert square_to_coords("h8") == (7, 7)

        with pytest.raises(ValueError):
            square_to_coords("i9")  # 无效坐标

    def test_coords_to_square(self):
        """测试坐标到方格转换"""
        assert coords_to_square(0, 0) == "a1"
        assert coords_to_square(4, 3) == "e4"
        assert coords_to_square(7, 7) == "h8"

        with pytest.raises(ValueError):
            coords_to_square(-1, 0)  # 无效坐标

    def test_get_piece_color(self):
        """测试获取棋子颜色"""
        assert get_piece_color(PieceType.WHITE_KING) == PieceColor.WHITE
        assert get_piece_color(PieceType.BLACK_QUEEN) == PieceColor.BLACK
        assert get_piece_color(PieceType.EMPTY) is None

    def test_is_valid_square(self):
        """测试方格坐标有效性"""
        assert is_valid_square("a1") is True
        assert is_valid_square("e4") is True
        assert is_valid_square("h8") is True
        assert is_valid_square("i9") is False
        assert is_valid_square("z0") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Stockfish引擎测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import chess

from shared.models.chess_models import AIAnalysis
from services.ai_service.src.ai.engine import StockfishEngine


class TestStockfishEngine:
    """Stockfish引擎测试类"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        return StockfishEngine()

    @pytest.fixture
    def mock_chess_engine(self):
        """模拟chess引擎"""
        engine_mock = Mock()
        engine_mock.configure = AsyncMock()
        engine_mock.play = AsyncMock()
        engine_mock.analyse = AsyncMock()
        engine_mock.quit = AsyncMock()
        return engine_mock

    def test_init(self, engine):
        """测试初始化"""
        assert engine.stockfish_path == "stockfish"
        assert engine.default_difficulty == 3
        assert not engine.is_running
        assert engine.difficulty_level == 3
        assert len(engine.difficulty_configs) == 10

    @pytest.mark.asyncio
    async def test_initialize_success(self, engine, mock_chess_engine):
        """测试初始化成功"""
        with patch('chess.engine.popen_uci', return_value=("transport", mock_chess_engine)):
            success = await engine.initialize()

            assert success
            assert engine.is_running
            assert engine.engine == mock_chess_engine

    @pytest.mark.asyncio
    async def test_initialize_failure(self, engine):
        """测试初始化失败"""
        with patch('chess.engine.popen_uci', side_effect=Exception("Stockfish not found")):
            success = await engine.initialize()

            assert not success
            assert not engine.is_running

    def test_set_difficulty(self, engine):
        """测试设置难度"""
        # 有效难度
        engine.set_difficulty(5)
        assert engine.difficulty_level == 5

        engine.set_difficulty(1)
        assert engine.difficulty_level == 1

        engine.set_difficulty(10)
        assert engine.difficulty_level == 10

        # 无效难度
        original_level = engine.difficulty_level
        engine.set_difficulty(11)
        assert engine.difficulty_level == original_level

        engine.set_difficulty(0)
        assert engine.difficulty_level == original_level

    def test_set_position_from_fen(self, engine):
        """测试从FEN设置位置"""
        # 初始位置
        initial_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        engine.set_position_from_fen(initial_fen)
        assert engine.current_board.fen() == initial_fen

        # 中局位置（chess库会自动处理en passant字段）
        middle_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2"
        engine.set_position_from_fen(middle_fen)
        # 检查基本棋盘布局是否正确
        assert "4p3/4P3" in engine.current_board.fen()

    def test_set_position_from_moves(self, engine):
        """测试从移动序列设置位置"""
        moves = ["e2e4", "e7e5", "g1f3", "b8c6"]
        engine.set_position_from_moves(moves)

        # 检查移动历史
        move_history = engine.get_move_history()
        assert move_history == moves

        # 检查棋盘状态
        assert len(engine.current_board.move_stack) == 4

    @pytest.mark.asyncio
    async def test_get_best_move(self, engine, mock_chess_engine):
        """测试获取最佳移动"""
        # 模拟引擎响应
        mock_result = Mock()
        mock_result.move = chess.Move.from_uci("e2e4")
        mock_chess_engine.play = AsyncMock(return_value=mock_result)

        # 模拟分析结果
        mock_analysis = {
            "score": Mock(),
            "depth": 8,
            "nodes": 12345,
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")]
        }
        mock_analysis["score"].is_mate.return_value = False
        mock_analysis["score"].score.return_value = 25  # 0.25 pawns
        mock_chess_engine.analyse = AsyncMock(return_value=mock_analysis)

        engine.engine = mock_chess_engine
        engine.is_running = True

        analysis = await engine.get_best_move()

        assert analysis is not None
        assert analysis.best_move == "e2e4"
        assert analysis.evaluation == 0.25
        assert analysis.depth == 8
        assert analysis.nodes == 12345
        assert len(analysis.principal_variation) == 2

    @pytest.mark.asyncio
    async def test_get_best_move_mate(self, engine, mock_chess_engine):
        """测试将死情况的最佳移动"""
        mock_result = Mock()
        mock_result.move = chess.Move.from_uci("d8h4")
        mock_chess_engine.play = AsyncMock(return_value=mock_result)

        # 模拟将死分析
        mock_analysis = {
            "score": Mock(),
            "depth": 5,
            "nodes": 5000,
            "pv": [chess.Move.from_uci("d8h4")]
        }
        mock_analysis["score"].is_mate.return_value = True
        mock_analysis["score"].mate.return_value = 1  # 1步将死
        mock_chess_engine.analyse = AsyncMock(return_value=mock_analysis)

        engine.engine = mock_chess_engine
        engine.is_running = True

        analysis = await engine.get_best_move()

        assert analysis is not None
        assert analysis.best_move == "d8h4"
        assert analysis.evaluation == 9999  # 将死评分

    @pytest.mark.asyncio
    async def test_get_best_move_no_engine(self, engine):
        """测试引擎未初始化时获取最佳移动"""
        analysis = await engine.get_best_move()
        assert analysis is None

    @pytest.mark.asyncio
    async def test_evaluate_position(self, engine, mock_chess_engine):
        """测试评估位置"""
        mock_analysis = {
            "score": Mock()
        }
        mock_analysis["score"].is_mate.return_value = False
        mock_analysis["score"].score.return_value = 150  # 1.5 pawns
        mock_chess_engine.analyse = AsyncMock(return_value=mock_analysis)

        engine.engine = mock_chess_engine
        engine.is_running = True

        evaluation = await engine.evaluate_position()
        assert evaluation == 1.5

    @pytest.mark.asyncio
    async def test_is_game_over(self, engine):
        """测试游戏结束检查"""
        # 正常游戏进行中
        is_over, result = await engine.is_game_over()
        assert not is_over
        assert result is None

        # 设置将死位置
        mate_fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        engine.set_position_from_fen(mate_fen)

        is_over, result = await engine.is_game_over()
        assert is_over
        assert "checkmate" in result

    def test_make_move(self, engine):
        """测试执行移动"""
        # 合法移动
        assert engine.make_move("e2e4")
        assert len(engine.current_board.move_stack) == 1

        # 非法移动
        assert not engine.make_move("e2e5")  # 无效移动
        assert len(engine.current_board.move_stack) == 1

    def test_undo_move(self, engine):
        """测试撤销移动"""
        # 没有移动可撤销
        assert not engine.undo_move()

        # 执行移动后撤销
        engine.make_move("e2e4")
        assert len(engine.current_board.move_stack) == 1

        assert engine.undo_move()
        assert len(engine.current_board.move_stack) == 0

    def test_get_legal_moves(self, engine):
        """测试获取合法移动"""
        legal_moves = engine.get_legal_moves()
        assert isinstance(legal_moves, list)
        assert len(legal_moves) == 20  # 初始位置有20个合法移动

        # 检查包含标准开局移动
        assert "e2e4" in legal_moves
        assert "d2d4" in legal_moves
        assert "g1f3" in legal_moves

    def test_is_move_legal(self, engine):
        """测试移动合法性检查"""
        # 合法移动
        assert engine.is_move_legal("e2e4")
        assert engine.is_move_legal("b1c3")

        # 非法移动
        assert not engine.is_move_legal("e2e5")
        assert not engine.is_move_legal("a1a8")

    def test_get_board_fen(self, engine):
        """测试获取FEN字符串"""
        initial_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        assert engine.get_board_fen() == initial_fen

        # 执行移动后检查FEN
        engine.make_move("e2e4")
        new_fen = engine.get_board_fen()
        assert "4P3" in new_fen  # 检查白兵在e4位置
        assert new_fen != initial_fen

    def test_get_move_history(self, engine):
        """测试获取移动历史"""
        # 初始为空
        assert engine.get_move_history() == []

        # 执行几步移动
        moves = ["e2e4", "e7e5", "g1f3"]
        for move in moves:
            engine.make_move(move)

        history = engine.get_move_history()
        assert history == moves

    @pytest.mark.asyncio
    async def test_suggest_moves(self, engine, mock_chess_engine):
        """测试移动建议"""
        # 模拟多变着分析
        mock_analysis = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": Mock(),
                "depth": 8
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": Mock(),
                "depth": 8
            },
            {
                "pv": [chess.Move.from_uci("g1f3")],
                "score": Mock(),
                "depth": 8
            }
        ]

        for i, analysis in enumerate(mock_analysis):
            analysis["score"].is_mate.return_value = False
            analysis["score"].score.return_value = 25 - i * 5  # 递减分数

        mock_chess_engine.analyse = AsyncMock(return_value=mock_analysis)

        engine.engine = mock_chess_engine
        engine.is_running = True

        suggestions = await engine.suggest_moves(3)

        assert len(suggestions) == 3
        assert suggestions[0]["move"] == "e2e4"
        assert suggestions[0]["rank"] == 1
        assert suggestions[1]["move"] == "d2d4"
        assert suggestions[2]["move"] == "g1f3"

    @pytest.mark.asyncio
    async def test_analyze_game(self, engine, mock_chess_engine):
        """测试整局分析"""
        moves = ["e2e4", "e7e5", "g1f3", "b8c6"]

        # 模拟最佳移动分析
        mock_results = [
            Mock(move=chess.Move.from_uci("e2e4")),
            Mock(move=chess.Move.from_uci("e7e5")),
            Mock(move=chess.Move.from_uci("g1f3")),
            Mock(move=chess.Move.from_uci("b8c6"))
        ]

        mock_chess_engine.play = AsyncMock(side_effect=mock_results)
        engine.engine = mock_chess_engine
        engine.is_running = True

        analysis = await engine.analyze_game(moves)

        assert analysis["total_moves"] == 4
        assert len(analysis["move_analysis"]) == 4
        assert analysis["accuracy"]["white"] == 1.0  # 所有移动都是最佳
        assert analysis["accuracy"]["black"] == 1.0

    def test_get_engine_info(self, engine):
        """测试获取引擎信息"""
        info = engine.get_engine_info()

        assert info["engine_path"] == "stockfish"
        assert info["is_running"] is False
        assert info["difficulty_level"] == 3
        assert info["hash_size"] == 128
        assert info["threads"] == 2
        assert "current_fen" in info
        assert "legal_moves_count" in info

    @pytest.mark.asyncio
    async def test_shutdown(self, engine, mock_chess_engine):
        """测试引擎关闭"""
        engine.engine = mock_chess_engine
        engine.is_running = True

        await engine.shutdown()

        mock_chess_engine.quit.assert_called_once()
        assert not engine.is_running


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
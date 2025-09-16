"""
游戏管理服务单元测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from shared.models.chess_models import GameState, GameEvent, Player, MoveResult
from services.game_manager.src.game.service import GameManagerService
from services.game_manager.src.game.state_machine import GameStateMachine


class TestGameManagerService:
    """游戏管理服务测试类"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return GameManagerService()

    @pytest.fixture
    def mock_database(self):
        """模拟数据库连接"""
        db = Mock()
        db.connect = AsyncMock(return_value=True)
        db.disconnect = AsyncMock()
        db.create_game = AsyncMock(return_value="game-123")
        db.get_game = AsyncMock(return_value={
            "id": "game-123",
            "status": "waiting",
            "white_player": "human",
            "black_player": "ai",
            "current_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "moves": [],
            "created_at": datetime.now()
        })
        db.update_game = AsyncMock(return_value=True)
        db.save_move = AsyncMock(return_value=True)
        return db

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

    @pytest.fixture
    def mock_state_machine(self):
        """模拟状态机"""
        state_machine = Mock(spec=GameStateMachine)
        state_machine.current_state = "waiting"
        state_machine.transition = Mock(return_value=True)
        state_machine.can_transition = Mock(return_value=True)
        state_machine.get_valid_actions = Mock(return_value=["start", "cancel"])
        return state_machine

    def test_init(self, service):
        """测试初始化"""
        assert service.service_name == "game_manager"
        assert service.state_machine is not None
        assert not service.is_running
        assert service.current_game_id is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, service, mock_database, mock_event_bus):
        """测试服务初始化成功"""
        service.database = mock_database

        with patch('services.game_manager.src.game.service.RedisEventBus', return_value=mock_event_bus):
            success = await service.initialize()

            assert success
            mock_event_bus.connect.assert_called_once()
            mock_database.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_database_failure(self, service, mock_event_bus):
        """测试数据库连接失败"""
        with patch('services.game_manager.src.game.service.RedisEventBus', return_value=mock_event_bus), \
             patch.object(service.database, 'connect', return_value=False):

            success = await service.initialize()
            assert not success

    @pytest.mark.asyncio
    async def test_create_game(self, service, mock_database, mock_state_machine):
        """测试创建游戏"""
        service.database = mock_database
        service.state_machine = mock_state_machine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        game_config = {
            "white_player": "human",
            "black_player": "ai",
            "ai_difficulty": 3,
            "time_limit": 600
        }

        game_id = await service.create_game(game_config)

        assert game_id == "game-123"
        mock_database.create_game.assert_called_once()
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_start_game_success(self, service, mock_database, mock_state_machine):
        """测试开始游戏成功"""
        service.database = mock_database
        service.state_machine = mock_state_machine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.current_game_id = "game-123"

        success = await service.start_game("game-123")

        assert success
        mock_state_machine.transition.assert_called_with("start")
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_start_game_invalid_state(self, service, mock_state_machine):
        """测试在无效状态下开始游戏"""
        service.state_machine = mock_state_machine
        mock_state_machine.can_transition.return_value = False

        success = await service.start_game("game-123")

        assert not success

    @pytest.mark.asyncio
    async def test_make_move_success(self, service, mock_database, mock_state_machine):
        """测试下棋成功"""
        service.database = mock_database
        service.state_machine = mock_state_machine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.current_game_id = "game-123"

        move_data = {
            "from_square": "e2",
            "to_square": "e4",
            "piece_type": "pawn",
            "player": "white"
        }

        with patch.object(service, '_validate_move', return_value=True), \
             patch.object(service, '_execute_move', return_value=MoveResult(
                 success=True,
                 move="e2e4",
                 new_fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                 is_checkmate=False,
                 is_stalemate=False
             )):

            result = await service.make_move("game-123", move_data)

            assert result.success
            service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_make_move_invalid(self, service, mock_state_machine):
        """测试无效下棋"""
        service.state_machine = mock_state_machine
        service.current_game_id = "game-123"

        move_data = {
            "from_square": "e2",
            "to_square": "e5",  # 无效移动
            "piece_type": "pawn",
            "player": "white"
        }

        with patch.object(service, '_validate_move', return_value=False):
            result = await service.make_move("game-123", move_data)

            assert not result.success

    @pytest.mark.asyncio
    async def test_handle_ai_move_request(self, service):
        """测试处理AI移动请求"""
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        event_data = {
            "data": {
                "game_id": "game-123",
                "position": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "difficulty": 3
            }
        }

        await service._handle_ai_move_request(event_data)

        # 检查AI引擎请求是否被发布
        service.event_bus.publish.assert_called()
        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "ai_analysis_request"

    @pytest.mark.asyncio
    async def test_handle_ai_move_result(self, service, mock_database):
        """测试处理AI移动结果"""
        service.database = mock_database
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.current_game_id = "game-123"

        event_data = {
            "data": {
                "game_id": "game-123",
                "best_move": "e7e5",
                "analysis": {
                    "evaluation": 0.2,
                    "depth": 10,
                    "nodes": 1000000,
                    "time": 3.5
                }
            }
        }

        with patch.object(service, '_execute_move', return_value=MoveResult(
            success=True,
            move="e7e5",
            new_fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            is_checkmate=False,
            is_stalemate=False
        )):
            await service._handle_ai_move_result(event_data)

            service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_handle_robot_move_complete(self, service, mock_database):
        """测试处理机器人移动完成"""
        service.database = mock_database
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        event_data = {
            "data": {
                "game_id": "game-123",
                "move": "e7e5",
                "success": True
            }
        }

        await service._handle_robot_move_complete(event_data)

        # 检查游戏状态更新是否被发布
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_pause_game(self, service, mock_state_machine):
        """测试暂停游戏"""
        service.state_machine = mock_state_machine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        success = await service.pause_game("game-123")

        assert success
        mock_state_machine.transition.assert_called_with("pause")
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_resume_game(self, service, mock_state_machine):
        """测试恢复游戏"""
        service.state_machine = mock_state_machine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        success = await service.resume_game("game-123")

        assert success
        mock_state_machine.transition.assert_called_with("resume")
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_end_game(self, service, mock_database, mock_state_machine):
        """测试结束游戏"""
        service.database = mock_database
        service.state_machine = mock_state_machine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        result = "draw"
        reason = "stalemate"

        success = await service.end_game("game-123", result, reason)

        assert success
        mock_state_machine.transition.assert_called_with("end")
        mock_database.update_game.assert_called()
        service.event_bus.publish.assert_called()

    def test_validate_move(self, service):
        """测试移动验证"""
        # 模拟当前棋局状态
        service.current_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

        # 有效移动
        valid_move = {
            "from_square": "e2",
            "to_square": "e4",
            "piece_type": "pawn",
            "player": "white"
        }

        with patch('chess.Board') as mock_board:
            mock_board.return_value.is_valid.return_value = True
            result = service._validate_move("game-123", valid_move)
            assert result

        # 无效移动
        invalid_move = {
            "from_square": "e2",
            "to_square": "e5",
            "piece_type": "pawn",
            "player": "white"
        }

        with patch('chess.Board') as mock_board:
            mock_board.return_value.is_valid.return_value = False
            result = service._validate_move("game-123", invalid_move)
            assert not result

    @pytest.mark.asyncio
    async def test_shutdown(self, service, mock_database, mock_event_bus):
        """测试服务关闭"""
        service.database = mock_database
        service.event_bus = mock_event_bus
        service.is_running = True

        await service.shutdown()

        assert not service.is_running
        mock_database.disconnect.assert_called_once()
        mock_event_bus.disconnect.assert_called_once()


class TestGameStateMachine:
    """游戏状态机测试类"""

    @pytest.fixture
    def state_machine(self):
        """创建状态机实例"""
        return GameStateMachine()

    def test_init(self, state_machine):
        """测试初始化"""
        assert state_machine.current_state == "idle"
        assert isinstance(state_machine.valid_transitions, dict)

    def test_can_transition_valid(self, state_machine):
        """测试有效状态转换"""
        state_machine.current_state = "waiting"
        assert state_machine.can_transition("start")

    def test_can_transition_invalid(self, state_machine):
        """测试无效状态转换"""
        state_machine.current_state = "playing"
        assert not state_machine.can_transition("start")

    def test_transition_success(self, state_machine):
        """测试状态转换成功"""
        state_machine.current_state = "waiting"

        result = state_machine.transition("start")

        assert result
        assert state_machine.current_state == "playing"

    def test_transition_failure(self, state_machine):
        """测试状态转换失败"""
        state_machine.current_state = "finished"

        result = state_machine.transition("start")

        assert not result
        assert state_machine.current_state == "finished"

    def test_get_valid_actions(self, state_machine):
        """测试获取有效动作"""
        state_machine.current_state = "waiting"
        actions = state_machine.get_valid_actions()

        assert "start" in actions
        assert "cancel" in actions

    def test_reset(self, state_machine):
        """测试重置状态机"""
        state_machine.current_state = "playing"

        state_machine.reset()

        assert state_machine.current_state == "idle"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
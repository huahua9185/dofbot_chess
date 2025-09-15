"""
AI服务测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from shared.models.chess_models import AIAnalysis
from services.ai_service.src.ai.service import AIService


class TestAIService:
    """AI服务测试类"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return AIService()

    @pytest.fixture
    def mock_engine(self):
        """模拟AI引擎"""
        engine = Mock()
        engine.initialize = AsyncMock(return_value=True)
        engine.shutdown = AsyncMock()
        engine.set_difficulty = Mock()
        engine.is_move_legal = Mock(return_value=True)
        engine.make_move = Mock(return_value=True)
        engine.get_best_move = AsyncMock(return_value=AIAnalysis(
            best_move="e2e4",
            evaluation=0.25,
            depth=8,
            nodes=12345,
            thinking_time=2.5,
            principal_variation=["e2e4", "e7e5"],
            confidence=0.9
        ))
        engine.evaluate_position = AsyncMock(return_value=0.5)
        engine.suggest_moves = AsyncMock(return_value=[
            {"move": "e2e4", "evaluation": 0.25, "rank": 1}
        ])
        engine.analyze_game = AsyncMock(return_value={
            "total_moves": 20,
            "accuracy": {"white": 0.8, "black": 0.7}
        })
        engine.is_game_over = AsyncMock(return_value=(False, None))
        engine.get_engine_info = Mock(return_value={
            "is_running": True,
            "difficulty_level": 3
        })
        engine.get_legal_moves = Mock(return_value=["e2e4", "d2d4", "g1f3"])
        engine.get_board_fen = Mock(return_value="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        engine.current_board = Mock()
        engine.current_board.move_stack = []
        engine.default_difficulty = 3
        return engine

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
        assert service.service_name == "ai_service"
        assert service.engine is not None
        assert not service.is_running
        assert service.current_game_id is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, service, mock_engine, mock_event_bus):
        """测试服务初始化成功"""
        service.engine = mock_engine

        with patch('services.ai_service.src.ai.service.RedisEventBus', return_value=mock_event_bus):
            success = await service.initialize()

            assert success
            mock_event_bus.connect.assert_called_once()
            mock_engine.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_redis_failure(self, service, mock_engine):
        """测试Redis连接失败"""
        service.engine = mock_engine

        with patch('services.ai_service.src.ai.service.RedisEventBus') as mock_bus_class:
            mock_bus = mock_bus_class.return_value
            mock_bus.connect = AsyncMock(return_value=False)

            success = await service.initialize()

            assert not success

    @pytest.mark.asyncio
    async def test_initialize_engine_failure(self, service, mock_event_bus):
        """测试引擎初始化失败"""
        with patch('services.ai_service.src.ai.service.RedisEventBus', return_value=mock_event_bus), \
             patch.object(service.engine, 'initialize', return_value=False):

            success = await service.initialize()

            assert not success

    @pytest.mark.asyncio
    async def test_handle_game_started(self, service, mock_engine):
        """测试处理游戏开始"""
        service.engine = mock_engine

        event_data = {
            "payload": {
                "game_id": "test_game_123",
                "ai_difficulty": 5
            }
        }

        await service._handle_game_started(event_data)

        assert service.current_game_id == "test_game_123"
        mock_engine.set_difficulty.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_handle_move_made(self, service, mock_engine):
        """测试处理移动执行"""
        service.engine = mock_engine

        event_data = {
            "payload": {
                "move": "e2e4",
                "player": "human"
            }
        }

        await service._handle_move_made(event_data)

        mock_engine.is_move_legal.assert_called_once_with("e2e4")
        mock_engine.make_move.assert_called_once_with("e2e4")

    @pytest.mark.asyncio
    async def test_handle_ai_move_request(self, service):
        """测试处理AI移动请求"""
        event_data = {
            "payload": {
                "time_limit": 5.0
            }
        }

        await service._handle_ai_move_request(event_data)

        # 检查请求是否加入队列
        assert not service.analysis_queue.empty()
        request = await service.analysis_queue.get()
        assert request["type"] == "move_request"
        assert request["time_limit"] == 5.0

    @pytest.mark.asyncio
    async def test_handle_difficulty_change(self, service, mock_engine):
        """测试处理难度变化"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        event_data = {
            "payload": {
                "difficulty": 7
            }
        }

        await service._handle_difficulty_change(event_data)

        mock_engine.set_difficulty.assert_called_once_with(7)

    @pytest.mark.asyncio
    async def test_handle_analysis_request(self, service):
        """测试处理分析请求"""
        event_data = {
            "payload": {
                "type": "position",
                "data": {}
            }
        }

        await service._handle_analysis_request(event_data)

        # 检查请求是否加入队列
        assert not service.analysis_queue.empty()
        request = await service.analysis_queue.get()
        assert request["type"] == "analysis_request"
        assert request["analysis_type"] == "position"

    @pytest.mark.asyncio
    async def test_process_ai_move_request(self, service, mock_engine):
        """测试处理AI移动请求"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.current_game_id = "test_game"

        request_data = {
            "time_limit": 3.0,
            "game_id": "test_game"
        }

        await service._process_ai_move_request(request_data)

        mock_engine.get_best_move.assert_called_once_with(3.0)
        mock_engine.make_move.assert_called_once()
        service.event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_process_ai_move_request_no_move(self, service, mock_engine):
        """测试AI无法找到移动的情况"""
        service.engine = mock_engine
        service.engine.get_best_move = AsyncMock(return_value=None)
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        request_data = {"time_limit": 3.0}

        await service._process_ai_move_request(request_data)

        # 应该发布错误事件
        service.event_bus.publish.assert_called()
        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "ai_error"

    @pytest.mark.asyncio
    async def test_process_analysis_request_position(self, service, mock_engine):
        """测试处理位置分析请求"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        request_data = {
            "analysis_type": "position",
            "data": {}
        }

        await service._process_analysis_request(request_data)

        mock_engine.evaluate_position.assert_called_once()
        service.event_bus.publish.assert_called()

        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "ai_analysis_result"
        assert call_args.payload["type"] == "position_analysis"

    @pytest.mark.asyncio
    async def test_process_analysis_request_suggestions(self, service, mock_engine):
        """测试处理移动建议请求"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        request_data = {
            "analysis_type": "suggestions",
            "data": {"count": 5}
        }

        await service._process_analysis_request(request_data)

        mock_engine.suggest_moves.assert_called_once_with(5)
        service.event_bus.publish.assert_called()

        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.payload["type"] == "move_suggestions"

    @pytest.mark.asyncio
    async def test_process_analysis_request_game(self, service, mock_engine):
        """测试处理整局分析请求"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        moves = ["e2e4", "e7e5", "g1f3", "b8c6"]
        request_data = {
            "analysis_type": "game",
            "data": {"moves": moves}
        }

        await service._process_analysis_request(request_data)

        mock_engine.analyze_game.assert_called_once_with(moves)
        service.event_bus.publish.assert_called()

        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.payload["type"] == "game_analysis"

    @pytest.mark.asyncio
    async def test_check_game_over(self, service, mock_engine):
        """测试检查游戏结束"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        # 游戏未结束
        mock_engine.is_game_over = AsyncMock(return_value=(False, None))
        await service._check_game_over()
        service.event_bus.publish.assert_not_called()

        # 游戏结束
        mock_engine.is_game_over = AsyncMock(return_value=(True, "checkmate_white"))
        await service._check_game_over()
        service.event_bus.publish.assert_called()

        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "game_over"

    @pytest.mark.asyncio
    async def test_publish_ai_move(self, service):
        """测试发布AI移动"""
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.current_game_id = "test_game"

        analysis = AIAnalysis(
            best_move="e2e4",
            evaluation=0.25,
            depth=8,
            nodes=12345,
            thinking_time=2.5,
            principal_variation=["e2e4", "e7e5"],
            confidence=0.9
        )

        await service._publish_ai_move(analysis)

        service.event_bus.publish.assert_called_once()
        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "ai_move_result"
        assert call_args.payload["game_id"] == "test_game"

    @pytest.mark.asyncio
    async def test_publish_ai_error(self, service):
        """测试发布AI错误"""
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.current_game_id = "test_game"

        await service._publish_ai_error("Test error message")

        service.event_bus.publish.assert_called_once()
        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "ai_error"
        assert call_args.payload["error"] == "Test error message"

    @pytest.mark.asyncio
    async def test_publish_engine_status(self, service, mock_engine):
        """测试发布引擎状态"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()

        await service._publish_engine_status()

        service.event_bus.publish.assert_called_once()
        call_args = service.event_bus.publish.call_args[0][0]
        assert call_args.event_type == "ai_status_update"
        assert call_args.source == "ai_service"

    @pytest.mark.asyncio
    async def test_analysis_processor(self, service, mock_engine):
        """测试分析处理器"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.is_running = True

        # 添加移动请求
        await service.analysis_queue.put({
            "type": "move_request",
            "time_limit": 3.0
        })

        # 运行一次处理循环
        with patch.object(service, '_process_ai_move_request') as mock_process:
            task = asyncio.create_task(service._analysis_processor())
            await asyncio.sleep(0.1)  # 让处理器运行一次
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_reporter(self, service, mock_engine):
        """测试状态报告器"""
        service.engine = mock_engine
        service.event_bus = Mock()
        service.event_bus.publish = AsyncMock()
        service.is_running = True

        # 运行一次报告循环
        with patch.object(service, '_publish_engine_status') as mock_publish:
            task = asyncio.create_task(service._status_reporter())
            await asyncio.sleep(0.1)  # 让报告器运行一次
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            mock_publish.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown(self, service, mock_engine, mock_event_bus):
        """测试服务关闭"""
        service.engine = mock_engine
        service.event_bus = mock_event_bus
        service.is_running = True

        await service.shutdown()

        assert not service.is_running
        mock_engine.shutdown.assert_called_once()
        mock_event_bus.disconnect.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
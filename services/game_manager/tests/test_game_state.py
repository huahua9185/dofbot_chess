"""
游戏状态机测试
"""
import pytest
from datetime import datetime

from src.game_state import (
    GameState, GameStateMachine, GameStatus, GameEvent, Player, MoveInfo
)


class TestGameState:
    """游戏状态测试类"""

    def test_game_state_creation(self):
        """测试游戏状态创建"""
        state = GameState()

        assert state.game_id is not None
        assert state.status == GameStatus.CREATED
        assert state.current_player == Player.WHITE
        assert state.human_player == Player.WHITE
        assert state.ai_player == Player.BLACK
        assert state.ai_difficulty == 3
        assert len(state.move_history) == 0
        assert state.winner is None

    def test_game_state_to_dict(self):
        """测试游戏状态序列化"""
        state = GameState()
        state_dict = state.to_dict()

        assert isinstance(state_dict, dict)
        assert "game_id" in state_dict
        assert "status" in state_dict
        assert "current_player" in state_dict
        assert "move_history" in state_dict


class TestGameStateMachine:
    """游戏状态机测试类"""

    def setup_method(self):
        """测试设置"""
        self.state_machine = GameStateMachine()
        self.game_state = GameState()

    def test_initial_state_transitions(self):
        """测试初始状态转换"""
        # 测试有效转换
        assert self.state_machine.can_transition(GameStatus.CREATED, GameEvent.START_GAME)
        assert self.state_machine.can_transition(GameStatus.CREATED, GameEvent.ABANDON_GAME)
        assert self.state_machine.can_transition(GameStatus.CREATED, GameEvent.GAME_ERROR)

        # 测试无效转换
        assert not self.state_machine.can_transition(GameStatus.CREATED, GameEvent.MAKE_MOVE)
        assert not self.state_machine.can_transition(GameStatus.CREATED, GameEvent.PAUSE_GAME)

    def test_playing_state_transitions(self):
        """测试游戏进行中状态转换"""
        # 测试有效转换
        assert self.state_machine.can_transition(GameStatus.PLAYING, GameEvent.MAKE_MOVE)
        assert self.state_machine.can_transition(GameStatus.PLAYING, GameEvent.AI_MOVE)
        assert self.state_machine.can_transition(GameStatus.PLAYING, GameEvent.PAUSE_GAME)
        assert self.state_machine.can_transition(GameStatus.PLAYING, GameEvent.END_GAME)
        assert self.state_machine.can_transition(GameStatus.PLAYING, GameEvent.CHECKMATE)

        # 测试无效转换
        assert not self.state_machine.can_transition(GameStatus.PLAYING, GameEvent.START_GAME)

    def test_finished_state_transitions(self):
        """测试完成状态转换"""
        # 完成状态不能转换到其他状态
        assert not self.state_machine.can_transition(GameStatus.FINISHED, GameEvent.START_GAME)
        assert not self.state_machine.can_transition(GameStatus.FINISHED, GameEvent.MAKE_MOVE)
        assert not self.state_machine.can_transition(GameStatus.FINISHED, GameEvent.RESUME_GAME)

    def test_get_valid_events(self):
        """测试获取有效事件"""
        created_events = self.state_machine.get_valid_events(GameStatus.CREATED)
        assert GameEvent.START_GAME in created_events
        assert GameEvent.ABANDON_GAME in created_events
        assert GameEvent.GAME_ERROR in created_events

        playing_events = self.state_machine.get_valid_events(GameStatus.PLAYING)
        assert GameEvent.MAKE_MOVE in playing_events
        assert GameEvent.AI_MOVE in playing_events
        assert GameEvent.PAUSE_GAME in playing_events

        finished_events = self.state_machine.get_valid_events(GameStatus.FINISHED)
        assert len(finished_events) == 0

    def test_state_handlers(self):
        """测试状态处理器"""
        handled_states = []

        def test_handler(game_state, old_status, **kwargs):
            handled_states.append((game_state.status, old_status))

        self.state_machine.register_state_handler(GameStatus.WAITING, test_handler)

        # 执行状态转换
        success = self.state_machine.process_event(self.game_state, GameEvent.START_GAME)

        assert success
        assert self.game_state.status == GameStatus.WAITING
        assert len(handled_states) == 1
        assert handled_states[0] == (GameStatus.WAITING, GameStatus.CREATED)

    def test_event_handlers(self):
        """测试事件处理器"""
        handled_events = []

        def test_handler(game_state, **kwargs):
            handled_events.append((GameEvent.START_GAME, kwargs))

        self.state_machine.register_event_handler(GameEvent.START_GAME, test_handler)

        # 执行事件处理
        success = self.state_machine.process_event(
            self.game_state, GameEvent.START_GAME, test_param="test_value"
        )

        assert success
        assert len(handled_events) == 1
        assert handled_events[0][0] == GameEvent.START_GAME
        assert handled_events[0][1]["test_param"] == "test_value"

    def test_error_handling(self):
        """测试错误处理"""
        def error_handler(game_state, **kwargs):
            raise Exception("Test error")

        self.state_machine.register_event_handler(GameEvent.START_GAME, error_handler)

        # 执行事件处理，应该触发错误
        success = self.state_machine.process_event(self.game_state, GameEvent.START_GAME)

        assert not success
        assert self.game_state.status == GameStatus.ERROR
        assert "Test error" in self.game_state.error_message

    def test_utility_methods(self):
        """测试工具方法"""
        # 测试游戏活跃状态检查
        assert self.state_machine.is_game_active(GameStatus.WAITING)
        assert self.state_machine.is_game_active(GameStatus.PLAYING)
        assert self.state_machine.is_game_active(GameStatus.PAUSED)
        assert not self.state_machine.is_game_active(GameStatus.FINISHED)
        assert not self.state_machine.is_game_active(GameStatus.ABANDONED)

        # 测试游戏完成状态检查
        assert self.state_machine.is_game_finished(GameStatus.FINISHED)
        assert self.state_machine.is_game_finished(GameStatus.ABANDONED)
        assert self.state_machine.is_game_finished(GameStatus.ERROR)
        assert not self.state_machine.is_game_finished(GameStatus.PLAYING)
        assert not self.state_machine.is_game_finished(GameStatus.WAITING)

        # 测试状态描述
        description = self.state_machine.get_status_description(GameStatus.PLAYING)
        assert "游戏进行中" in description


class TestMoveInfo:
    """移动信息测试类"""

    def test_move_info_creation(self):
        """测试移动信息创建"""
        move = MoveInfo(
            move="e2e4",
            player=Player.WHITE,
            timestamp=datetime.now(),
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            san="e4",
            uci="e2e4",
            is_capture=False,
            is_check=False,
            is_checkmate=False,
            piece_moved="P",
            from_square="e2",
            to_square="e4"
        )

        assert move.move == "e2e4"
        assert move.player == Player.WHITE
        assert move.fen is not None
        assert move.san == "e4"
        assert move.uci == "e2e4"
        assert not move.is_capture
        assert not move.is_check
        assert not move.is_checkmate
        assert move.piece_moved == "P"
        assert move.from_square == "e2"
        assert move.to_square == "e4"


if __name__ == "__main__":
    pytest.main([__file__])
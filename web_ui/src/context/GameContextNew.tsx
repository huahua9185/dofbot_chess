/**
 * 重构的游戏状态Context
 * 基于API客户端的游戏管理
 */

import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import apiClient from '../services/api.client';
import {
  GameCreateRequest,
  GameStatus,
  MoveRequest,
  AIAnalysisRequest
} from '../services/api.types';
import { useWebSocket } from './WebSocketContext';

// ===== 状态类型定义 =====
interface GameState {
  // 基础游戏信息
  gameId: string | null;
  status: 'waiting' | 'playing' | 'paused' | 'finished' | 'error';
  currentPlayer: 'white' | 'black';
  humanColor: 'white' | 'black';
  aiColor: 'white' | 'black';

  // 棋盘状态
  boardFen: string;
  moveHistory: string[];
  lastMove: string | null;
  moveCount: number;

  // AI设置
  aiDifficulty: number;
  aiAnalysis: any | null;

  // 时间控制
  timeControl: {
    initial_time: number;
    increment: number;
  } | null;

  // 状态管理
  isLoading: boolean;
  error: string | null;
  lastUpdate: number;
}

// ===== Action类型定义 =====
type GameAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'CREATE_GAME'; payload: { gameId: string; humanColor: 'white' | 'black'; aiDifficulty: number } }
  | { type: 'UPDATE_GAME_STATUS'; payload: GameStatus }
  | { type: 'MAKE_MOVE'; payload: { move: string; player: string } }
  | { type: 'SET_AI_DIFFICULTY'; payload: number }
  | { type: 'SET_AI_ANALYSIS'; payload: any }
  | { type: 'SET_STATUS'; payload: GameState['status'] }
  | { type: 'SET_CURRENT_PLAYER'; payload: 'white' | 'black' }
  | { type: 'UPDATE_BOARD'; payload: { fen: string } }
  | { type: 'RESET_GAME' };

// ===== Context类型定义 =====
interface GameContextType {
  state: GameState;
  actions: {
    createGame: (config: GameCreateRequest) => Promise<void>;
    startGame: () => Promise<void>;
    pauseGame: () => Promise<void>;
    endGame: () => Promise<void>;
    makeMove: (move: string) => Promise<void>;
    setAIDifficulty: (difficulty: number) => Promise<void>;
    requestAIAnalysis: (request: AIAnalysisRequest) => Promise<void>;
    refreshGameStatus: () => Promise<void>;
    resetGame: () => void;
  };
}

// ===== 初始状态 =====
const initialState: GameState = {
  gameId: null,
  status: 'waiting',
  currentPlayer: 'white',
  humanColor: 'white',
  aiColor: 'black',
  boardFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  moveHistory: [],
  lastMove: null,
  moveCount: 0,
  aiDifficulty: 3,
  aiAnalysis: null,
  timeControl: null,
  isLoading: false,
  error: null,
  lastUpdate: 0,
};

// ===== Reducer =====
function gameReducer(state: GameState, action: GameAction): GameState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };

    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };

    case 'CREATE_GAME':
      return {
        ...state,
        gameId: action.payload.gameId,
        humanColor: action.payload.humanColor,
        aiColor: action.payload.humanColor === 'white' ? 'black' : 'white',
        aiDifficulty: action.payload.aiDifficulty,
        status: 'waiting',
        lastUpdate: Date.now(),
      };

    case 'UPDATE_GAME_STATUS':
      return {
        ...state,
        status: action.payload.status as GameState['status'],
        currentPlayer: action.payload.current_player as 'white' | 'black',
        boardFen: action.payload.board_fen,
        moveCount: action.payload.move_count,
        lastMove: action.payload.last_move || null,
        lastUpdate: Date.now(),
      };

    case 'MAKE_MOVE':
      return {
        ...state,
        moveHistory: [...state.moveHistory, action.payload.move],
        lastMove: action.payload.move,
        currentPlayer: action.payload.player === 'white' ? 'black' : 'white',
        lastUpdate: Date.now(),
      };

    case 'SET_AI_DIFFICULTY':
      return { ...state, aiDifficulty: action.payload };

    case 'SET_AI_ANALYSIS':
      return { ...state, aiAnalysis: action.payload };

    case 'SET_STATUS':
      return { ...state, status: action.payload };

    case 'SET_CURRENT_PLAYER':
      return { ...state, currentPlayer: action.payload };

    case 'UPDATE_BOARD':
      return { ...state, boardFen: action.payload.fen };

    case 'RESET_GAME':
      return initialState;

    default:
      return state;
  }
}

// ===== Context创建 =====
const GameContext = createContext<GameContextType | undefined>(undefined);

// ===== Provider组件 =====
interface GameProviderProps {
  children: ReactNode;
}

export const GameProvider: React.FC<GameProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const { connect, disconnect, onMessage } = useWebSocket();

  // ===== Actions =====
  const createGame = async (config: GameCreateRequest) => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await apiClient.createGame(config);

      dispatch({
        type: 'CREATE_GAME',
        payload: {
          gameId: response.game_id,
          humanColor: config.human_color,
          aiDifficulty: config.ai_difficulty
        }
      });

      // 连接游戏WebSocket
      connect(response.game_id);

      dispatch({ type: 'SET_ERROR', payload: null });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '创建游戏失败' });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const startGame = async () => {
    if (!state.gameId) {
      dispatch({ type: 'SET_ERROR', payload: '未找到游戏ID' });
      return;
    }

    try {
      await apiClient.startGame(state.gameId);
      dispatch({ type: 'SET_STATUS', payload: 'playing' });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '开始游戏失败' });
    }
  };

  const pauseGame = async () => {
    if (!state.gameId) {
      dispatch({ type: 'SET_ERROR', payload: '未找到游戏ID' });
      return;
    }

    try {
      await apiClient.pauseGame(state.gameId);
      dispatch({ type: 'SET_STATUS', payload: 'paused' });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '暂停游戏失败' });
    }
  };

  const endGame = async () => {
    if (!state.gameId) {
      dispatch({ type: 'SET_ERROR', payload: '未找到游戏ID' });
      return;
    }

    try {
      await apiClient.endGame(state.gameId);
      dispatch({ type: 'SET_STATUS', payload: 'finished' });
      disconnect();
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '结束游戏失败' });
    }
  };

  const makeMove = async (move: string) => {
    if (!state.gameId) {
      dispatch({ type: 'SET_ERROR', payload: '未找到游戏ID' });
      return;
    }

    try {
      const moveRequest: MoveRequest = {
        move,
        player: state.currentPlayer,
      };

      await apiClient.makeMove(state.gameId, moveRequest);

      dispatch({
        type: 'MAKE_MOVE',
        payload: {
          move,
          player: state.currentPlayer
        }
      });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '移动失败' });
    }
  };

  const setAIDifficulty = async (difficulty: number) => {
    if (!state.gameId) {
      dispatch({ type: 'SET_ERROR', payload: '未找到游戏ID' });
      return;
    }

    try {
      await apiClient.setAIDifficulty(state.gameId, difficulty);
      dispatch({ type: 'SET_AI_DIFFICULTY', payload: difficulty });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '设置AI难度失败' });
    }
  };

  const requestAIAnalysis = async (request: AIAnalysisRequest) => {
    try {
      const response = await apiClient.requestAIAnalysis(request);
      dispatch({ type: 'SET_AI_ANALYSIS', payload: response.analysis });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'AI分析失败' });
    }
  };

  const refreshGameStatus = async () => {
    if (!state.gameId) return;

    try {
      const gameStatus = await apiClient.getGameStatus(state.gameId);
      dispatch({ type: 'UPDATE_GAME_STATUS', payload: gameStatus });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '获取游戏状态失败' });
    }
  };

  const resetGame = () => {
    disconnect();
    dispatch({ type: 'RESET_GAME' });
  };

  // ===== WebSocket消息监听 =====
  useEffect(() => {
    const unsubscribe = onMessage((message) => {
      switch (message.type) {
        case 'game_status':
          dispatch({ type: 'UPDATE_GAME_STATUS', payload: message.data });
          break;
        case 'move_broadcast':
          dispatch({
            type: 'MAKE_MOVE',
            payload: {
              move: message.data.move,
              player: message.data.player
            }
          });
          dispatch({
            type: 'UPDATE_BOARD',
            payload: { fen: message.data.board_fen }
          });
          break;
        case 'ai_move_result':
          dispatch({
            type: 'MAKE_MOVE',
            payload: {
              move: message.data.move,
              player: state.aiColor
            }
          });
          dispatch({ type: 'SET_AI_ANALYSIS', payload: message.data.analysis });
          break;
      }
    });

    return unsubscribe;
  }, [onMessage, state.aiColor]);

  // ===== Context值 =====
  const contextValue: GameContextType = {
    state,
    actions: {
      createGame,
      startGame,
      pauseGame,
      endGame,
      makeMove,
      setAIDifficulty,
      requestAIAnalysis,
      refreshGameStatus,
      resetGame,
    },
  };

  return (
    <GameContext.Provider value={contextValue}>
      {children}
    </GameContext.Provider>
  );
};

// ===== Hook =====
export const useGame = () => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};
import React, { createContext, useContext, useReducer, ReactNode } from 'react';

// 游戏状态类型
export interface GameState {
  gameId: string | null;
  status: 'waiting' | 'playing' | 'paused' | 'finished' | 'error';
  currentPlayer: 'white' | 'black';
  humanColor: 'white' | 'black';
  aiColor: 'white' | 'black';
  boardFen: string;
  moveHistory: string[];
  lastMove: string | null;
  aiDifficulty: number;
  isLoading: boolean;
  error: string | null;
}

// 动作类型
type GameAction =
  | { type: 'CREATE_GAME'; payload: { gameId: string; humanColor: 'white' | 'black'; aiDifficulty: number } }
  | { type: 'START_GAME' }
  | { type: 'MAKE_MOVE'; payload: { move: string; player: string } }
  | { type: 'UPDATE_BOARD'; payload: { fen: string } }
  | { type: 'SET_STATUS'; payload: 'waiting' | 'playing' | 'paused' | 'finished' | 'error' }
  | { type: 'SET_CURRENT_PLAYER'; payload: 'white' | 'black' }
  | { type: 'SET_AI_DIFFICULTY'; payload: number }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'RESET_GAME' };

// 初始状态
const initialState: GameState = {
  gameId: null,
  status: 'waiting',
  currentPlayer: 'white',
  humanColor: 'white',
  aiColor: 'black',
  boardFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  moveHistory: [],
  lastMove: null,
  aiDifficulty: 3,
  isLoading: false,
  error: null,
};

// 减少器函数
const gameReducer = (state: GameState, action: GameAction): GameState => {
  switch (action.type) {
    case 'CREATE_GAME':
      return {
        ...state,
        gameId: action.payload.gameId,
        humanColor: action.payload.humanColor,
        aiColor: action.payload.humanColor === 'white' ? 'black' : 'white',
        aiDifficulty: action.payload.aiDifficulty,
        status: 'waiting',
        error: null,
      };

    case 'START_GAME':
      return {
        ...state,
        status: 'playing',
        error: null,
      };

    case 'MAKE_MOVE':
      return {
        ...state,
        moveHistory: [...state.moveHistory, action.payload.move],
        lastMove: action.payload.move,
        currentPlayer: state.currentPlayer === 'white' ? 'black' : 'white',
        error: null,
      };

    case 'UPDATE_BOARD':
      return {
        ...state,
        boardFen: action.payload.fen,
      };

    case 'SET_STATUS':
      return {
        ...state,
        status: action.payload,
      };

    case 'SET_CURRENT_PLAYER':
      return {
        ...state,
        currentPlayer: action.payload,
      };

    case 'SET_AI_DIFFICULTY':
      return {
        ...state,
        aiDifficulty: action.payload,
      };

    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };

    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
        isLoading: false,
      };

    case 'RESET_GAME':
      return {
        ...initialState,
      };

    default:
      return state;
  }
};

// Context类型
interface GameContextType {
  state: GameState;
  dispatch: React.Dispatch<GameAction>;
  createGame: (humanColor: 'white' | 'black', aiDifficulty: number) => Promise<void>;
  startGame: () => Promise<void>;
  makeMove: (move: string, player: string) => Promise<void>;
  pauseGame: () => Promise<void>;
  endGame: () => Promise<void>;
  setAIDifficulty: (difficulty: number) => Promise<void>;
  resetGame: () => void;
}

// 创建Context
const GameContext = createContext<GameContextType | undefined>(undefined);

// Provider组件
interface GameProviderProps {
  children: ReactNode;
}

export const GameProvider: React.FC<GameProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(gameReducer, initialState);

  // API基础URL
  const API_BASE = process.env.NODE_ENV === 'production'
    ? ''
    : 'http://localhost:8080';

  // 创建游戏
  const createGame = async (humanColor: 'white' | 'black', aiDifficulty: number) => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });

      const response = await fetch(`${API_BASE}/api/v1/games`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          human_color: humanColor,
          ai_difficulty: aiDifficulty,
        }),
      });

      if (!response.ok) {
        throw new Error('创建游戏失败');
      }

      const data = await response.json();
      dispatch({
        type: 'CREATE_GAME',
        payload: {
          gameId: data.game_id,
          humanColor,
          aiDifficulty
        }
      });

    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : '创建游戏失败'
      });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  // 开始游戏
  const startGame = async () => {
    if (!state.gameId) return;

    try {
      dispatch({ type: 'SET_LOADING', payload: true });

      const response = await fetch(`${API_BASE}/api/v1/games/${state.gameId}/start`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('开始游戏失败');
      }

      dispatch({ type: 'START_GAME' });

    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : '开始游戏失败'
      });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  // 执行移动
  const makeMove = async (move: string, player: string) => {
    if (!state.gameId) return;

    try {
      const response = await fetch(`${API_BASE}/api/v1/games/${state.gameId}/moves`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          move,
          player,
        }),
      });

      if (!response.ok) {
        throw new Error('移动执行失败');
      }

      dispatch({ type: 'MAKE_MOVE', payload: { move, player } });

    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : '移动执行失败'
      });
    }
  };

  // 暂停游戏
  const pauseGame = async () => {
    if (!state.gameId) return;

    try {
      const response = await fetch(`${API_BASE}/api/v1/games/${state.gameId}/pause`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('暂停游戏失败');
      }

      dispatch({ type: 'SET_STATUS', payload: 'paused' });

    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : '暂停游戏失败'
      });
    }
  };

  // 结束游戏
  const endGame = async () => {
    if (!state.gameId) return;

    try {
      const response = await fetch(`${API_BASE}/api/v1/games/${state.gameId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('结束游戏失败');
      }

      dispatch({ type: 'SET_STATUS', payload: 'finished' });

    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : '结束游戏失败'
      });
    }
  };

  // 设置AI难度
  const setAIDifficulty = async (difficulty: number) => {
    if (!state.gameId) {
      dispatch({ type: 'SET_AI_DIFFICULTY', payload: difficulty });
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/v1/ai/difficulty/${state.gameId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ difficulty }),
      });

      if (!response.ok) {
        throw new Error('设置AI难度失败');
      }

      dispatch({ type: 'SET_AI_DIFFICULTY', payload: difficulty });

    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : '设置AI难度失败'
      });
    }
  };

  // 重置游戏
  const resetGame = () => {
    dispatch({ type: 'RESET_GAME' });
  };

  const value: GameContextType = {
    state,
    dispatch,
    createGame,
    startGame,
    makeMove,
    pauseGame,
    endGame,
    setAIDifficulty,
    resetGame,
  };

  return (
    <GameContext.Provider value={value}>
      {children}
    </GameContext.Provider>
  );
};

// Hook
export const useGame = () => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};
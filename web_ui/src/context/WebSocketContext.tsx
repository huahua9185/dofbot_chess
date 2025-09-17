import React, { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';

// WebSocket状态类型
export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

// 消息类型
export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp?: number;
}

// Context类型
interface WebSocketContextType {
  socket: Socket | null;
  status: WebSocketStatus;
  gameId: string | null;
  systemConnected: boolean;
  connect: (gameId?: string) => void;
  disconnect: () => void;
  connectSystem: () => void;
  disconnectSystem: () => void;
  sendMessage: (message: WebSocketMessage) => void;
  onMessage: (callback: (message: WebSocketMessage) => void) => () => void;
  onSystemMessage: (callback: (message: WebSocketMessage) => void) => () => void;
}

// 创建Context
const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

// Provider组件
interface WebSocketProviderProps {
  children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [gameId, setGameId] = useState<string | null>(null);
  const [systemConnected, setSystemConnected] = useState(false);

  const socketRef = useRef<Socket | null>(null);
  const systemSocketRef = useRef<Socket | null>(null);
  const messageCallbacks = useRef<Set<(message: WebSocketMessage) => void>>(new Set());
  const systemMessageCallbacks = useRef<Set<(message: WebSocketMessage) => void>>(new Set());

  // WebSocket基础URL
  const WS_BASE = process.env.NODE_ENV === 'production'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    : 'ws://localhost:8000';

  // 连接游戏WebSocket
  const connect = (newGameId?: string) => {
    if (socketRef.current?.connected) {
      disconnect();
    }

    const targetGameId = newGameId || gameId;
    if (!targetGameId) {
      console.error('GameID is required for WebSocket connection');
      return;
    }

    try {
      setStatus('connecting');
      setGameId(targetGameId);

      socketRef.current = io(`${WS_BASE}/ws/${targetGameId}`, {
        transports: ['websocket', 'polling'],
        upgrade: true,
        timeout: 10000,
      });

      socketRef.current.on('connect', () => {
        console.log('WebSocket connected to game:', targetGameId);
        setStatus('connected');
      });

      socketRef.current.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason);
        setStatus('disconnected');
      });

      socketRef.current.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        setStatus('error');
      });

      socketRef.current.on('message', (message: WebSocketMessage) => {
        messageCallbacks.current.forEach(callback => {
          try {
            callback(message);
          } catch (error) {
            console.error('Error in message callback:', error);
          }
        });
      });

      // 处理各种游戏事件
      socketRef.current.on('move_broadcast', (data) => {
        const message: WebSocketMessage = {
          type: 'move_broadcast',
          data,
          timestamp: Date.now()
        };
        messageCallbacks.current.forEach(callback => callback(message));
      });

      socketRef.current.on('game_status', (data) => {
        const message: WebSocketMessage = {
          type: 'game_status',
          data,
          timestamp: Date.now()
        };
        messageCallbacks.current.forEach(callback => callback(message));
      });

      socketRef.current.on('ai_move_result', (data) => {
        const message: WebSocketMessage = {
          type: 'ai_move_result',
          data,
          timestamp: Date.now()
        };
        messageCallbacks.current.forEach(callback => callback(message));
      });

      socketRef.current.on('robot_status_update', (data) => {
        const message: WebSocketMessage = {
          type: 'robot_status_update',
          data,
          timestamp: Date.now()
        };
        messageCallbacks.current.forEach(callback => callback(message));
      });

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setStatus('error');
    }
  };

  // 断开游戏WebSocket
  const disconnect = () => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setStatus('disconnected');
    setGameId(null);
  };

  // 连接系统监控WebSocket
  const connectSystem = () => {
    if (systemSocketRef.current?.connected) {
      disconnectSystem();
    }

    try {
      systemSocketRef.current = io(`${WS_BASE}/ws/system`, {
        transports: ['websocket', 'polling'],
        upgrade: true,
      });

      systemSocketRef.current.on('connect', () => {
        console.log('System WebSocket connected');
        setSystemConnected(true);
      });

      systemSocketRef.current.on('disconnect', () => {
        console.log('System WebSocket disconnected');
        setSystemConnected(false);
      });

      systemSocketRef.current.on('system_metrics', (data) => {
        const message: WebSocketMessage = {
          type: 'system_metrics',
          data,
          timestamp: Date.now()
        };
        systemMessageCallbacks.current.forEach(callback => callback(message));
      });

      systemSocketRef.current.on('heartbeat', (data) => {
        const message: WebSocketMessage = {
          type: 'heartbeat',
          data,
          timestamp: Date.now()
        };
        systemMessageCallbacks.current.forEach(callback => callback(message));
      });

    } catch (error) {
      console.error('Failed to connect system WebSocket:', error);
    }
  };

  // 断开系统监控WebSocket
  const disconnectSystem = () => {
    if (systemSocketRef.current) {
      systemSocketRef.current.disconnect();
      systemSocketRef.current = null;
    }
    setSystemConnected(false);
  };

  // 发送消息
  const sendMessage = (message: WebSocketMessage) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('message', message);
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  };

  // 订阅游戏消息
  const onMessage = (callback: (message: WebSocketMessage) => void) => {
    messageCallbacks.current.add(callback);

    // 返回取消订阅函数
    return () => {
      messageCallbacks.current.delete(callback);
    };
  };

  // 订阅系统消息
  const onSystemMessage = (callback: (message: WebSocketMessage) => void) => {
    systemMessageCallbacks.current.add(callback);

    // 返回取消订阅函数
    return () => {
      systemMessageCallbacks.current.delete(callback);
    };
  };

  // 清理连接
  useEffect(() => {
    return () => {
      disconnect();
      disconnectSystem();
    };
  }, []);

  // 心跳检测
  useEffect(() => {
    if (status === 'connected' && socketRef.current) {
      const heartbeat = setInterval(() => {
        if (socketRef.current?.connected) {
          socketRef.current.emit('ping');
        }
      }, 30000); // 每30秒发送心跳

      return () => clearInterval(heartbeat);
    }
  }, [status]);

  const value: WebSocketContextType = {
    socket: socketRef.current,
    status,
    gameId,
    systemConnected,
    connect,
    disconnect,
    connectSystem,
    disconnectSystem,
    sendMessage,
    onMessage,
    onSystemMessage,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

// Hook
export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};
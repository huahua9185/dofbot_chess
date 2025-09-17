/**
 * 系统状态Context
 * 管理系统监控、健康检查等相关状态
 */

import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import apiClient from '../services/api.client';
import { SystemStatus, HealthCheck, RobotStatus, VisionStatus } from '../services/api.types';
import { useWebSocket } from './WebSocketContext';

// ===== 状态类型定义 =====
interface SystemState {
  systemStatus: SystemStatus | null;
  healthCheck: HealthCheck | null;
  robotStatus: RobotStatus['robot_status'];
  visionStatus: VisionStatus['vision_status'];
  loading: boolean;
  error: string | null;
  lastUpdate: number;
}

// ===== Action类型定义 =====
type SystemAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_SYSTEM_STATUS'; payload: SystemStatus }
  | { type: 'SET_HEALTH_CHECK'; payload: HealthCheck }
  | { type: 'SET_ROBOT_STATUS'; payload: RobotStatus['robot_status'] }
  | { type: 'SET_VISION_STATUS'; payload: VisionStatus['vision_status'] }
  | { type: 'SET_LAST_UPDATE'; payload: number }
  | { type: 'RESET_STATE' };

// ===== Context类型定义 =====
interface SystemContextType {
  state: SystemState;
  actions: {
    refreshSystemStatus: () => Promise<void>;
    refreshHealthCheck: () => Promise<void>;
    refreshRobotStatus: () => Promise<void>;
    refreshVisionStatus: () => Promise<void>;
    refreshAllStatus: () => Promise<void>;
    sendRobotCommand: (command: any) => Promise<void>;
    emergencyStop: () => Promise<void>;
    calibrateVision: () => Promise<void>;
  };
}

// ===== 初始状态 =====
const initialState: SystemState = {
  systemStatus: null,
  healthCheck: null,
  robotStatus: null,
  visionStatus: null,
  loading: false,
  error: null,
  lastUpdate: 0,
};

// ===== Reducer =====
function systemReducer(state: SystemState, action: SystemAction): SystemState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, loading: false };
    case 'SET_SYSTEM_STATUS':
      return { ...state, systemStatus: action.payload, lastUpdate: Date.now() };
    case 'SET_HEALTH_CHECK':
      return { ...state, healthCheck: action.payload, lastUpdate: Date.now() };
    case 'SET_ROBOT_STATUS':
      return { ...state, robotStatus: action.payload, lastUpdate: Date.now() };
    case 'SET_VISION_STATUS':
      return { ...state, visionStatus: action.payload, lastUpdate: Date.now() };
    case 'SET_LAST_UPDATE':
      return { ...state, lastUpdate: action.payload };
    case 'RESET_STATE':
      return initialState;
    default:
      return state;
  }
}

// ===== Context创建 =====
const SystemContext = createContext<SystemContextType | undefined>(undefined);

// ===== Provider组件 =====
interface SystemProviderProps {
  children: ReactNode;
}

export const SystemProvider: React.FC<SystemProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(systemReducer, initialState);
  const { connectSystem, onSystemMessage } = useWebSocket();

  // ===== Actions =====
  const refreshSystemStatus = async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const data = await apiClient.getSystemStatus();
      dispatch({ type: 'SET_SYSTEM_STATUS', payload: data });
      dispatch({ type: 'SET_ERROR', payload: null });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '获取系统状态失败' });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const refreshHealthCheck = async () => {
    try {
      const data = await apiClient.getHealthCheck();
      dispatch({ type: 'SET_HEALTH_CHECK', payload: data });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '健康检查失败' });
    }
  };

  const refreshRobotStatus = async () => {
    try {
      const data = await apiClient.getRobotStatus();
      dispatch({ type: 'SET_ROBOT_STATUS', payload: data.robot_status });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '获取机器人状态失败' });
    }
  };

  const refreshVisionStatus = async () => {
    try {
      const data = await apiClient.getVisionStatus();
      dispatch({ type: 'SET_VISION_STATUS', payload: data.vision_status });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '获取视觉状态失败' });
    }
  };

  const refreshAllStatus = async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const data = await apiClient.getAllStatus();

      dispatch({ type: 'SET_SYSTEM_STATUS', payload: data.system });
      dispatch({ type: 'SET_HEALTH_CHECK', payload: data.health });
      dispatch({ type: 'SET_ROBOT_STATUS', payload: data.robot.robot_status });
      dispatch({ type: 'SET_VISION_STATUS', payload: data.vision.vision_status });
      dispatch({ type: 'SET_ERROR', payload: null });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '获取状态失败' });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const sendRobotCommand = async (command: any) => {
    try {
      await apiClient.sendRobotCommand(command);
      // 发送命令后刷新机器人状态
      setTimeout(refreshRobotStatus, 500);
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '发送机器人命令失败' });
    }
  };

  const emergencyStop = async () => {
    try {
      await apiClient.emergencyStop();
      setTimeout(refreshRobotStatus, 500);
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '紧急停止失败' });
    }
  };

  const calibrateVision = async () => {
    try {
      await apiClient.calibrateVision();
      setTimeout(refreshVisionStatus, 1000);
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : '视觉标定失败' });
    }
  };

  // ===== WebSocket监听 =====
  useEffect(() => {
    // 连接系统监控WebSocket
    connectSystem();

    // 监听系统消息
    const unsubscribe = onSystemMessage((message) => {
      switch (message.type) {
        case 'system_metrics':
          dispatch({ type: 'SET_SYSTEM_STATUS', payload: message.data });
          break;
        case 'robot_status_update':
          dispatch({ type: 'SET_ROBOT_STATUS', payload: message.data });
          break;
        case 'heartbeat':
          dispatch({ type: 'SET_LAST_UPDATE', payload: Date.now() });
          break;
      }
    });

    return unsubscribe;
  }, [connectSystem, onSystemMessage]);

  // ===== 定期刷新 =====
  useEffect(() => {
    // 初始加载
    refreshAllStatus();

    // 定期刷新（每30秒）
    const interval = setInterval(() => {
      refreshAllStatus();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // ===== Context值 =====
  const contextValue: SystemContextType = {
    state,
    actions: {
      refreshSystemStatus,
      refreshHealthCheck,
      refreshRobotStatus,
      refreshVisionStatus,
      refreshAllStatus,
      sendRobotCommand,
      emergencyStop,
      calibrateVision,
    },
  };

  return (
    <SystemContext.Provider value={contextValue}>
      {children}
    </SystemContext.Provider>
  );
};

// ===== Hook =====
export const useSystem = () => {
  const context = useContext(SystemContext);
  if (!context) {
    throw new Error('useSystem must be used within a SystemProvider');
  }
  return context;
};
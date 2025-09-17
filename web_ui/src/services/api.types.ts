/**
 * API类型定义文件
 * 基于后端API端点定义的TypeScript接口
 */

// ===== 基础类型 =====
export interface ApiResponse<T> {
  data?: T;
  message?: string;
  status?: string;
}

// ===== 系统监控相关 =====
export interface SystemStatus {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  gpu_usage: number;
  temperature: number;
  services_status: {
    vision_service: string;
    robot_service: string;
    ai_service: string;
    web_gateway: string;
  };
}

export interface HealthCheck {
  status: string;
  timestamp: number;
  services: {
    web_gateway: string;
    redis: string;
    game_coordinator: string;
  };
}

export interface SystemLogs {
  logs: string[];
  lines: number;
}

// ===== 游戏管理相关 =====
export interface GameCreateRequest {
  human_color: 'white' | 'black';
  ai_difficulty: number;
  time_control?: {
    initial_time: number;
    increment: number;
  };
}

export interface GameCreateResponse {
  game_id: string;
  message: string;
  status: string;
}

export interface GameStatus {
  game_id: string;
  status: string;
  current_player: string;
  board_fen: string;
  move_count: number;
  last_move?: string;
}

export interface MoveRequest {
  move: string;
  player: string;
}

export interface MoveResponse {
  message: string;
  status: string;
}

// ===== AI分析相关 =====
export interface AIAnalysisRequest {
  analysis_type: string;
  position_fen: string;
  moves?: string[];
  depth?: number;
}

export interface AIAnalysisResponse {
  analysis: any;
  status: string;
}

export interface AIDifficultyRequest {
  difficulty: number;
}

export interface AIDifficultyResponse {
  message: string;
  difficulty: number;
}

// ===== 机器人控制相关 =====
export interface RobotCommand {
  command_type: string;
  from_position?: [number, number, number];
  to_position?: [number, number, number];
  speed?: number;
  precision?: number;
  timeout?: number;
}

export interface RobotCommandResponse {
  message: string;
  status: string;
}

export interface RobotStatus {
  robot_status: {
    position: [number, number, number];
    status: string;
    is_moving: boolean;
    last_command_time: number;
  } | null;
}

export interface EmergencyStopResponse {
  message: string;
  status: string;
}

// ===== 视觉系统相关 =====
export interface VisionStatus {
  vision_status: any;
}

export interface VisionCalibrateResponse {
  message: string;
  status: string;
}

// ===== WebSocket消息类型 =====
export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp?: number;
}

export interface SystemMetrics {
  type: 'system_metrics';
  data: SystemStatus;
  timestamp: number;
}

export interface GameStatusUpdate {
  type: 'game_status';
  data: GameStatus;
  timestamp: number;
}

export interface MoveUpdate {
  type: 'move_broadcast';
  data: {
    move: string;
    player: string;
    board_fen: string;
  };
  timestamp: number;
}

export interface RobotStatusUpdate {
  type: 'robot_status_update';
  data: RobotStatus['robot_status'];
  timestamp: number;
}

export interface AIResultUpdate {
  type: 'ai_move_result';
  data: {
    move: string;
    evaluation: number;
    analysis: any;
  };
  timestamp: number;
}

// ===== API错误类型 =====
export interface ApiError {
  detail: string;
  status_code?: number;
}
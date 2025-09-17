/**
 * API客户端服务
 * 统一的HTTP请求封装，基于后端API端点
 */

import {
  SystemStatus,
  HealthCheck,
  SystemLogs,
  GameCreateRequest,
  GameCreateResponse,
  GameStatus,
  MoveRequest,
  MoveResponse,
  AIAnalysisRequest,
  AIAnalysisResponse,
  AIDifficultyResponse,
  RobotCommand,
  RobotCommandResponse,
  RobotStatus,
  EmergencyStopResponse,
  VisionStatus,
  VisionCalibrateResponse,
  ApiError
} from './api.types';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || (
      process.env.NODE_ENV === 'production'
        ? '/api/v1'
        : 'http://localhost:8000/api/v1'
    );
  }

  // ===== 私有方法 =====
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorData: ApiError = await response.json().catch(() => ({
          detail: `HTTP ${response.status}: ${response.statusText}`
        }));
        throw new Error(errorData.detail || '请求失败');
      }

      return await response.json();
    } catch (error) {
      console.error(`API请求失败 [${endpoint}]:`, error);
      throw error;
    }
  }

  private async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  private async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  private async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  // ===== 系统监控API =====
  async getSystemStatus(): Promise<SystemStatus> {
    return this.get<SystemStatus>('/system/status');
  }

  async getHealthCheck(): Promise<HealthCheck> {
    return this.get<HealthCheck>('/health');
  }

  async getSystemLogs(lines: number = 100, service?: string): Promise<SystemLogs> {
    const params = new URLSearchParams({ lines: lines.toString() });
    if (service) params.append('service', service);

    return this.get<SystemLogs>(`/system/logs?${params.toString()}`);
  }

  // ===== 游戏管理API =====
  async createGame(request: GameCreateRequest): Promise<GameCreateResponse> {
    return this.post<GameCreateResponse>('/games', request);
  }

  async getGameStatus(gameId: string): Promise<GameStatus> {
    return this.get<GameStatus>(`/games/${gameId}`);
  }

  async makeMove(gameId: string, request: MoveRequest): Promise<MoveResponse> {
    return this.post<MoveResponse>(`/games/${gameId}/moves`, request);
  }

  async startGame(gameId: string): Promise<{ message: string; status: string }> {
    return this.post<{ message: string; status: string }>(`/games/${gameId}/start`);
  }

  async pauseGame(gameId: string): Promise<{ message: string; status: string }> {
    return this.post<{ message: string; status: string }>(`/games/${gameId}/pause`);
  }

  async endGame(gameId: string): Promise<{ message: string; status: string }> {
    return this.delete<{ message: string; status: string }>(`/games/${gameId}`);
  }

  // ===== AI分析API =====
  async requestAIAnalysis(request: AIAnalysisRequest): Promise<AIAnalysisResponse> {
    return this.post<AIAnalysisResponse>('/ai/analyze', request);
  }

  async setAIDifficulty(gameId: string, difficulty: number): Promise<AIDifficultyResponse> {
    return this.post<AIDifficultyResponse>(`/ai/difficulty/${gameId}`, { difficulty });
  }

  // ===== 机器人控制API =====
  async sendRobotCommand(command: RobotCommand): Promise<RobotCommandResponse> {
    return this.post<RobotCommandResponse>('/robot/command', command);
  }

  async getRobotStatus(): Promise<RobotStatus> {
    return this.get<RobotStatus>('/robot/status');
  }

  async emergencyStop(): Promise<EmergencyStopResponse> {
    return this.post<EmergencyStopResponse>('/robot/emergency_stop');
  }

  // ===== 视觉系统API =====
  async getVisionStatus(): Promise<VisionStatus> {
    return this.get<VisionStatus>('/vision/status');
  }

  async calibrateVision(): Promise<VisionCalibrateResponse> {
    return this.post<VisionCalibrateResponse>('/vision/calibrate');
  }

  // ===== 批量操作 =====
  async getAllStatus(): Promise<{
    system: SystemStatus;
    health: HealthCheck;
    robot: RobotStatus;
    vision: VisionStatus;
  }> {
    const [system, health, robot, vision] = await Promise.all([
      this.getSystemStatus(),
      this.getHealthCheck(),
      this.getRobotStatus(),
      this.getVisionStatus(),
    ]);

    return { system, health, robot, vision };
  }

  // ===== WebSocket连接辅助方法 =====
  getWebSocketUrl(gameId?: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = process.env.NODE_ENV === 'production'
      ? window.location.host
      : 'localhost:8000';

    if (gameId) {
      return `${protocol}//${host}/ws/${gameId}`;
    } else {
      return `${protocol}//${host}/ws/system`;
    }
  }
}

// 创建单例实例
const apiClient = new ApiClient();

export default apiClient;
export { ApiClient };
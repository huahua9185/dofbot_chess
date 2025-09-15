import React, { useEffect, useState } from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  Avatar,
  IconButton,
  Divider,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  Memory as MemoryIcon,
  Thermostat as ThermostatIcon,
  Storage as StorageIcon,
  Visibility as VisionIcon,
  SmartToy as RobotIcon,
  Psychology as AIIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

import { useGame } from '../context/GameContext';
import { useWebSocket } from '../context/WebSocketContext';

interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  gpu_usage: number;
  temperature: number;
  timestamp: number;
}

const DashboardPage: React.FC = () => {
  const { state: gameState } = useGame();
  const { connectSystem, onSystemMessage, systemConnected } = useWebSocket();
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics>({
    cpu_usage: 0,
    memory_usage: 0,
    disk_usage: 0,
    gpu_usage: 0,
    temperature: 0,
    timestamp: Date.now(),
  });
  const [metricsHistory, setMetricsHistory] = useState<SystemMetrics[]>([]);

  useEffect(() => {
    // 连接系统监控WebSocket
    connectSystem();

    // 订阅系统消息
    const unsubscribe = onSystemMessage((message) => {
      if (message.type === 'system_metrics') {
        const metrics = message.data as SystemMetrics;
        setSystemMetrics(metrics);

        // 更新历史数据（保留最近20个数据点）
        setMetricsHistory(prev => {
          const newHistory = [...prev, metrics];
          return newHistory.slice(-20);
        });
      }
    });

    // 获取初始数据
    fetchSystemStatus();

    return () => {
      unsubscribe();
    };
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const response = await fetch('/api/v1/system/status');
      if (response.ok) {
        const data = await response.json();
        setSystemMetrics({
          cpu_usage: data.cpu_usage,
          memory_usage: data.memory_usage,
          disk_usage: data.disk_usage,
          gpu_usage: data.gpu_usage,
          temperature: data.temperature,
          timestamp: Date.now(),
        });
      }
    } catch (error) {
      console.error('Failed to fetch system status:', error);
    }
  };

  const getStatusColor = (value: number, thresholds: number[] = [50, 80]) => {
    if (value < thresholds[0]) return '#4caf50'; // green
    if (value < thresholds[1]) return '#ff9800'; // orange
    return '#f44336'; // red
  };

  const pieData = [
    { name: 'CPU', value: systemMetrics.cpu_usage, color: '#2196f3' },
    { name: 'Memory', value: systemMetrics.memory_usage, color: '#4caf50' },
    { name: 'Disk', value: systemMetrics.disk_usage, color: '#ff9800' },
    { name: 'GPU', value: systemMetrics.gpu_usage, color: '#9c27b0' },
  ];

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* 页面标题 */}
      <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" component="h1" fontWeight={600}>
          系统仪表板
        </Typography>
        <Box>
          <IconButton onClick={fetchSystemStatus} color="primary">
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* 游戏状态卡片 */}
        <Grid item xs={12} md={6} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Avatar sx={{ bgcolor: 'primary.main', mr: 2 }}>
                  <PlayIcon />
                </Avatar>
                <Box>
                  <Typography variant="h6">当前游戏</Typography>
                  <Typography variant="body2" color="text.secondary">
                    游戏状态管理
                  </Typography>
                </Box>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">状态:</Typography>
                  <Chip
                    label={gameState.status === 'waiting' ? '等待中' :
                           gameState.status === 'playing' ? '游戏中' :
                           gameState.status === 'paused' ? '暂停' : '结束'}
                    color={gameState.status === 'playing' ? 'success' : 'default'}
                    size="small"
                  />
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">当前玩家:</Typography>
                  <Chip
                    label={gameState.currentPlayer === 'white' ? '白方' : '黑方'}
                    color={gameState.currentPlayer === 'white' ? 'default' : 'secondary'}
                    size="small"
                  />
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">AI难度:</Typography>
                  <Typography variant="body2" fontWeight={500}>
                    {gameState.aiDifficulty} 级
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">移动次数:</Typography>
                  <Typography variant="body2" fontWeight={500}>
                    {gameState.moveHistory.length}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* 系统性能卡片 */}
        <Grid item xs={12} md={6} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Avatar sx={{ bgcolor: 'success.main', mr: 2 }}>
                  <MemoryIcon />
                </Avatar>
                <Box>
                  <Typography variant="h6">系统性能</Typography>
                  <Typography variant="body2" color="text.secondary">
                    实时性能监控
                  </Typography>
                </Box>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">CPU使用率</Typography>
                    <Typography variant="body2" fontWeight={500}>
                      {systemMetrics.cpu_usage.toFixed(1)}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={systemMetrics.cpu_usage}
                    sx={{
                      '& .MuiLinearProgress-bar': {
                        backgroundColor: getStatusColor(systemMetrics.cpu_usage),
                      },
                    }}
                  />
                </Box>

                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">内存使用率</Typography>
                    <Typography variant="body2" fontWeight={500}>
                      {systemMetrics.memory_usage.toFixed(1)}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={systemMetrics.memory_usage}
                    sx={{
                      '& .MuiLinearProgress-bar': {
                        backgroundColor: getStatusColor(systemMetrics.memory_usage),
                      },
                    }}
                  />
                </Box>

                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">GPU使用率</Typography>
                    <Typography variant="body2" fontWeight={500}>
                      {systemMetrics.gpu_usage.toFixed(1)}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={systemMetrics.gpu_usage}
                    sx={{
                      '& .MuiLinearProgress-bar': {
                        backgroundColor: getStatusColor(systemMetrics.gpu_usage),
                      },
                    }}
                  />
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">系统温度:</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <ThermostatIcon sx={{ fontSize: 16, mr: 0.5, color: 'warning.main' }} />
                    <Typography variant="body2" fontWeight={500}>
                      {systemMetrics.temperature.toFixed(1)}°C
                    </Typography>
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* 服务状态卡片 */}
        <Grid item xs={12} md={6} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Avatar sx={{ bgcolor: 'info.main', mr: 2 }}>
                  <TrendingUpIcon />
                </Avatar>
                <Box>
                  <Typography variant="h6">服务状态</Typography>
                  <Typography variant="body2" color="text.secondary">
                    微服务监控
                  </Typography>
                </Box>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <VisionIcon sx={{ fontSize: 20, mr: 1, color: 'primary.main' }} />
                    <Typography variant="body2">视觉识别服务</Typography>
                  </Box>
                  <Chip label="运行中" color="success" size="small" />
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <RobotIcon sx={{ fontSize: 20, mr: 1, color: 'secondary.main' }} />
                    <Typography variant="body2">机器人控制服务</Typography>
                  </Box>
                  <Chip label="运行中" color="success" size="small" />
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <AIIcon sx={{ fontSize: 20, mr: 1, color: 'warning.main' }} />
                    <Typography variant="body2">AI引擎服务</Typography>
                  </Box>
                  <Chip label="运行中" color="success" size="small" />
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <StorageIcon sx={{ fontSize: 20, mr: 1, color: 'info.main' }} />
                    <Typography variant="body2">数据存储服务</Typography>
                  </Box>
                  <Chip
                    label={systemConnected ? '已连接' : '未连接'}
                    color={systemConnected ? 'success' : 'error'}
                    size="small"
                  />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* 性能趋势图表 */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 2, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              系统性能趋势
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={metricsHistory}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                />
                <YAxis domain={[0, 100]} />
                <Tooltip
                  labelFormatter={(value) => new Date(value).toLocaleTimeString()}
                  formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
                />
                <Line
                  type="monotone"
                  dataKey="cpu_usage"
                  stroke="#2196f3"
                  strokeWidth={2}
                  name="CPU"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="memory_usage"
                  stroke="#4caf50"
                  strokeWidth={2}
                  name="内存"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="gpu_usage"
                  stroke="#9c27b0"
                  strokeWidth={2}
                  name="GPU"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* 资源分布饼图 */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 2, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              资源使用分布
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

export default DashboardPage;
import React, { useState, useEffect } from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  Button,
  Switch,
  FormControlLabel,
  Alert,
  Chip,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItem,
  ListItemText,
  TextField,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  PlayArrow as StartIcon,
  Stop as StopIcon,
  RestartAlt as RestartIcon,
  Settings as SettingsIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Visibility as VisionIcon,
  SmartToy as RobotIcon,
  Psychology as AIIcon,
  Storage as StorageIcon,
  ViewList as LogsIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';

import { useWebSocket } from '../context/WebSocketContext';

interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'error';
  uptime: string;
  cpu_usage: number;
  memory_usage: number;
  last_error?: string;
}

interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  gpu_usage: number;
  temperature: number;
  timestamp: number;
}

const SystemPage: React.FC = () => {
  const { connectSystem, onSystemMessage, systemConnected } = useWebSocket();
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'vision_service', status: 'running', uptime: '2h 35m', cpu_usage: 15.2, memory_usage: 24.8 },
    { name: 'robot_service', status: 'running', uptime: '2h 35m', cpu_usage: 8.3, memory_usage: 12.1 },
    { name: 'ai_service', status: 'running', uptime: '2h 35m', cpu_usage: 45.1, memory_usage: 38.7 },
    { name: 'web_gateway', status: 'running', uptime: '2h 35m', cpu_usage: 5.2, memory_usage: 16.3 },
  ]);

  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics>({
    cpu_usage: 0,
    memory_usage: 0,
    disk_usage: 0,
    gpu_usage: 0,
    temperature: 0,
    timestamp: Date.now(),
  });

  const [metricsHistory, setMetricsHistory] = useState<SystemMetrics[]>([]);
  const [logsDialogOpen, setLogsDialogOpen] = useState(false);
  const [systemLogs, setSystemLogs] = useState<string[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // 连接系统监控
  useEffect(() => {
    connectSystem();

    const unsubscribe = onSystemMessage((message) => {
      if (message.type === 'system_metrics') {
        const metrics = message.data as SystemMetrics;
        setSystemMetrics(metrics);

        setMetricsHistory(prev => {
          const newHistory = [...prev, metrics];
          return newHistory.slice(-50); // 保留最近50个数据点
        });
      }
    });

    return unsubscribe;
  }, []);

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchSystemStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  // 获取系统状态
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

  // 获取系统日志
  const fetchSystemLogs = async () => {
    try {
      const response = await fetch('/api/v1/system/logs?lines=100');
      if (response.ok) {
        const data = await response.json();
        setSystemLogs(data.logs || []);
      }
    } catch (error) {
      console.error('Failed to fetch system logs:', error);
    }
  };

  // 控制服务
  const controlService = async (serviceName: string, action: 'start' | 'stop' | 'restart') => {
    try {
      const response = await fetch(`/api/v1/system/services/${serviceName}/${action}`, {
        method: 'POST',
      });

      if (response.ok) {
        // 刷新服务状态
        setTimeout(fetchSystemStatus, 1000);
      }
    } catch (error) {
      console.error(`Failed to ${action} service:`, error);
    }
  };

  // 紧急停止
  const emergencyStop = async () => {
    try {
      await fetch('/api/v1/robot/emergency_stop', { method: 'POST' });
    } catch (error) {
      console.error('Emergency stop failed:', error);
    }
  };

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <CheckCircleIcon color="success" />;
      case 'error':
        return <ErrorIcon color="error" />;
      default:
        return <WarningIcon color="warning" />;
    }
  };

  // 获取服务显示名称
  const getServiceDisplayName = (name: string) => {
    switch (name) {
      case 'vision_service':
        return '视觉识别服务';
      case 'robot_service':
        return '机器人控制服务';
      case 'ai_service':
        return 'AI引擎服务';
      case 'web_gateway':
        return 'Web网关服务';
      default:
        return name;
    }
  };

  // 获取服务图标
  const getServiceIcon = (name: string) => {
    switch (name) {
      case 'vision_service':
        return <VisionIcon color="primary" />;
      case 'robot_service':
        return <RobotIcon color="secondary" />;
      case 'ai_service':
        return <AIIcon color="warning" />;
      case 'web_gateway':
        return <StorageIcon color="info" />;
      default:
        return <SettingsIcon />;
    }
  };

  // 获取使用率颜色
  const getUsageColor = (value: number) => {
    if (value < 50) return 'success';
    if (value < 80) return 'warning';
    return 'error';
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* 页面标题 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" component="h1" fontWeight={600}>
          系统监控
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
            }
            label="自动刷新"
          />
          <Button
            variant="outlined"
            startIcon={<LogsIcon />}
            onClick={() => {
              fetchSystemLogs();
              setLogsDialogOpen(true);
            }}
          >
            系统日志
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={emergencyStop}
          >
            紧急停止
          </Button>
          <IconButton onClick={fetchSystemStatus} color="primary">
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {/* 连接状态提示 */}
      {!systemConnected && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          系统监控连接断开，数据可能不是最新的
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* 系统概览卡片 */}
        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                CPU使用率
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Box sx={{ width: '100%', mr: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={systemMetrics.cpu_usage}
                    color={getUsageColor(systemMetrics.cpu_usage)}
                  />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {systemMetrics.cpu_usage.toFixed(1)}%
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                内存使用率
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Box sx={{ width: '100%', mr: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={systemMetrics.memory_usage}
                    color={getUsageColor(systemMetrics.memory_usage)}
                  />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {systemMetrics.memory_usage.toFixed(1)}%
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                GPU使用率
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Box sx={{ width: '100%', mr: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={systemMetrics.gpu_usage}
                    color={getUsageColor(systemMetrics.gpu_usage)}
                  />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {systemMetrics.gpu_usage.toFixed(1)}%
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6} lg={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                系统温度
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 40 }}>
                <Typography variant="h4" color="warning.main">
                  {systemMetrics.temperature.toFixed(1)}°C
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* 服务状态表格 */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              服务状态
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>服务</TableCell>
                    <TableCell>状态</TableCell>
                    <TableCell>运行时间</TableCell>
                    <TableCell>CPU</TableCell>
                    <TableCell>内存</TableCell>
                    <TableCell>操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {services.map((service) => (
                    <TableRow key={service.name}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          {getServiceIcon(service.name)}
                          <Typography sx={{ ml: 1 }}>
                            {getServiceDisplayName(service.name)}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          {getStatusIcon(service.status)}
                          <Chip
                            label={service.status === 'running' ? '运行中' : '已停止'}
                            color={service.status === 'running' ? 'success' : 'error'}
                            size="small"
                            sx={{ ml: 1 }}
                          />
                        </Box>
                      </TableCell>
                      <TableCell>{service.uptime}</TableCell>
                      <TableCell>{service.cpu_usage?.toFixed(1)}%</TableCell>
                      <TableCell>{service.memory_usage?.toFixed(1)}%</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          {service.status === 'running' ? (
                            <Tooltip title="停止服务">
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => controlService(service.name, 'stop')}
                              >
                                <StopIcon />
                              </IconButton>
                            </Tooltip>
                          ) : (
                            <Tooltip title="启动服务">
                              <IconButton
                                size="small"
                                color="success"
                                onClick={() => controlService(service.name, 'start')}
                              >
                                <StartIcon />
                              </IconButton>
                            </Tooltip>
                          )}
                          <Tooltip title="重启服务">
                            <IconButton
                              size="small"
                              color="warning"
                              onClick={() => controlService(service.name, 'restart')}
                            >
                              <RestartIcon />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* 实时监控图表 */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 2, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              实时性能监控
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <AreaChart data={metricsHistory}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(value) => new Date(value).toLocaleTimeString().slice(0, -3)}
                />
                <YAxis domain={[0, 100]} />
                <ChartTooltip
                  labelFormatter={(value) => new Date(value).toLocaleTimeString()}
                  formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
                />
                <Area
                  type="monotone"
                  dataKey="cpu_usage"
                  stackId="1"
                  stroke="#2196f3"
                  fill="#2196f3"
                  fillOpacity={0.6}
                  name="CPU"
                />
                <Area
                  type="monotone"
                  dataKey="memory_usage"
                  stackId="2"
                  stroke="#4caf50"
                  fill="#4caf50"
                  fillOpacity={0.6}
                  name="内存"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* 详细性能图表 */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              系统性能历史
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={metricsHistory}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(value) => new Date(value).toLocaleTimeString().slice(0, -3)}
                />
                <YAxis domain={[0, 100]} />
                <ChartTooltip
                  labelFormatter={(value) => new Date(value).toLocaleTimeString()}
                  formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
                />
                <Line
                  type="monotone"
                  dataKey="cpu_usage"
                  stroke="#2196f3"
                  strokeWidth={2}
                  name="CPU使用率"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="memory_usage"
                  stroke="#4caf50"
                  strokeWidth={2}
                  name="内存使用率"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="gpu_usage"
                  stroke="#9c27b0"
                  strokeWidth={2}
                  name="GPU使用率"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
      </Grid>

      {/* 系统日志对话框 */}
      <Dialog open={logsDialogOpen} onClose={() => setLogsDialogOpen(false)} maxWidth="lg" fullWidth>
        <DialogTitle>系统日志</DialogTitle>
        <DialogContent>
          <Box sx={{ height: 400, overflow: 'auto', bgcolor: '#f5f5f5', p: 1, borderRadius: 1 }}>
            {systemLogs.length === 0 ? (
              <Typography color="text.secondary" textAlign="center">
                暂无日志数据
              </Typography>
            ) : (
              systemLogs.map((log, index) => (
                <Typography
                  key={index}
                  component="pre"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.75rem',
                    lineHeight: 1.2,
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                  }}
                >
                  {log}
                </Typography>
              ))
            )}
          </Box>
        </DialogContent>
      </Dialog>
    </Container>
  );
};

export default SystemPage;
/**
 * 机器人控制面板组件
 * 基于新API客户端的机器人控制界面
 */

import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  TextField,
  Grid,
  Chip,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Slider,
} from '@mui/material';
import {
  SmartToy as RobotIcon,
  Stop as StopIcon,
  PlayArrow as MoveIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';

import { useSystem } from '../../context/SystemContext';
import { RobotCommand } from '../../services/api.types';

const RobotControlPanel: React.FC = () => {
  const { state: systemState, actions: systemActions } = useSystem();
  const [commandDialogOpen, setCommandDialogOpen] = useState(false);
  const [commandForm, setCommandForm] = useState({
    command_type: 'move',
    from_position: [0, 0, 100] as [number, number, number],
    to_position: [100, 100, 100] as [number, number, number],
    speed: 50,
    precision: 1.0,
    timeout: 30.0,
  });

  const handleSendCommand = async () => {
    try {
      const command: RobotCommand = {
        command_type: commandForm.command_type,
        from_position: commandForm.from_position,
        to_position: commandForm.to_position,
        speed: commandForm.speed,
        precision: commandForm.precision,
        timeout: commandForm.timeout,
      };

      await systemActions.sendRobotCommand(command);
      setCommandDialogOpen(false);
    } catch (error) {
      console.error('发送机器人命令失败:', error);
    }
  };

  const handleEmergencyStop = async () => {
    try {
      await systemActions.emergencyStop();
    } catch (error) {
      console.error('紧急停止失败:', error);
    }
  };

  const getRobotStatusColor = () => {
    if (!systemState.robotStatus) return 'default';
    const status = systemState.robotStatus.status;
    if (status === 'idle') return 'success';
    if (status === 'moving') return 'primary';
    if (status === 'error') return 'error';
    return 'default';
  };

  const getRobotStatusText = () => {
    if (!systemState.robotStatus) return '未知状态';
    return systemState.robotStatus.status === 'idle' ? '空闲' :
           systemState.robotStatus.status === 'moving' ? '移动中' :
           systemState.robotStatus.status === 'error' ? '错误' : '未知';
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <RobotIcon sx={{ mr: 1, color: 'secondary.main' }} />
          <Typography variant="h6">机器人控制</Typography>
        </Box>

        {systemState.error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {systemState.error}
          </Alert>
        )}

        <Grid container spacing={2}>
          {/* 机器人状态显示 */}
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="body2">当前状态:</Typography>
              <Chip
                label={getRobotStatusText()}
                color={getRobotStatusColor()}
                size="small"
              />
            </Box>
          </Grid>

          {/* 位置信息 */}
          {systemState.robotStatus && (
            <Grid item xs={12}>
              <Typography variant="body2" gutterBottom>当前位置:</Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Chip label={`X: ${systemState.robotStatus.position[0]}`} size="small" variant="outlined" />
                <Chip label={`Y: ${systemState.robotStatus.position[1]}`} size="small" variant="outlined" />
                <Chip label={`Z: ${systemState.robotStatus.position[2]}`} size="small" variant="outlined" />
              </Box>
            </Grid>
          )}

          {/* 控制按钮 */}
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={<MoveIcon />}
                onClick={() => setCommandDialogOpen(true)}
                disabled={systemState.loading || systemState.robotStatus?.is_moving}
              >
                移动命令
              </Button>

              <Button
                variant="outlined"
                color="error"
                startIcon={<StopIcon />}
                onClick={handleEmergencyStop}
                disabled={systemState.loading}
              >
                紧急停止
              </Button>

              <Button
                variant="outlined"
                startIcon={systemState.loading ? <CircularProgress size={16} /> : <RefreshIcon />}
                onClick={systemActions.refreshRobotStatus}
                disabled={systemState.loading}
              >
                刷新状态
              </Button>
            </Box>
          </Grid>

          {/* 运动状态指示 */}
          {systemState.robotStatus?.is_moving && (
            <Grid item xs={12}>
              <Alert severity="info" icon={<CircularProgress size={20} />}>
                机器人正在执行移动操作...
              </Alert>
            </Grid>
          )}
        </Grid>

        {/* 命令发送对话框 */}
        <Dialog open={commandDialogOpen} onClose={() => setCommandDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>发送机器人命令</DialogTitle>
          <DialogContent>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="命令类型"
                  value={commandForm.command_type}
                  onChange={(e) => setCommandForm({...commandForm, command_type: e.target.value})}
                  select
                  SelectProps={{ native: true }}
                >
                  <option value="move">移动</option>
                  <option value="pick">抓取</option>
                  <option value="place">放置</option>
                  <option value="home">归位</option>
                </TextField>
              </Grid>

              <Grid item xs={4}>
                <TextField
                  fullWidth
                  label="起始X"
                  type="number"
                  value={commandForm.from_position[0]}
                  onChange={(e) => setCommandForm({
                    ...commandForm,
                    from_position: [parseInt(e.target.value), commandForm.from_position[1], commandForm.from_position[2]]
                  })}
                />
              </Grid>
              <Grid item xs={4}>
                <TextField
                  fullWidth
                  label="起始Y"
                  type="number"
                  value={commandForm.from_position[1]}
                  onChange={(e) => setCommandForm({
                    ...commandForm,
                    from_position: [commandForm.from_position[0], parseInt(e.target.value), commandForm.from_position[2]]
                  })}
                />
              </Grid>
              <Grid item xs={4}>
                <TextField
                  fullWidth
                  label="起始Z"
                  type="number"
                  value={commandForm.from_position[2]}
                  onChange={(e) => setCommandForm({
                    ...commandForm,
                    from_position: [commandForm.from_position[0], commandForm.from_position[1], parseInt(e.target.value)]
                  })}
                />
              </Grid>

              <Grid item xs={4}>
                <TextField
                  fullWidth
                  label="目标X"
                  type="number"
                  value={commandForm.to_position[0]}
                  onChange={(e) => setCommandForm({
                    ...commandForm,
                    to_position: [parseInt(e.target.value), commandForm.to_position[1], commandForm.to_position[2]]
                  })}
                />
              </Grid>
              <Grid item xs={4}>
                <TextField
                  fullWidth
                  label="目标Y"
                  type="number"
                  value={commandForm.to_position[1]}
                  onChange={(e) => setCommandForm({
                    ...commandForm,
                    to_position: [commandForm.to_position[0], parseInt(e.target.value), commandForm.to_position[2]]
                  })}
                />
              </Grid>
              <Grid item xs={4}>
                <TextField
                  fullWidth
                  label="目标Z"
                  type="number"
                  value={commandForm.to_position[2]}
                  onChange={(e) => setCommandForm({
                    ...commandForm,
                    to_position: [commandForm.to_position[0], commandForm.to_position[1], parseInt(e.target.value)]
                  })}
                />
              </Grid>

              <Grid item xs={12}>
                <Typography gutterBottom>移动速度: {commandForm.speed}%</Typography>
                <Slider
                  value={commandForm.speed}
                  onChange={(_, value) => setCommandForm({...commandForm, speed: value as number})}
                  min={1}
                  max={100}
                  marks
                  valueLabelDisplay="auto"
                />
              </Grid>

              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="精度"
                  type="number"
                  value={commandForm.precision}
                  onChange={(e) => setCommandForm({...commandForm, precision: parseFloat(e.target.value)})}
                  inputProps={{ step: 0.1, min: 0.1, max: 10 }}
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="超时时间(秒)"
                  type="number"
                  value={commandForm.timeout}
                  onChange={(e) => setCommandForm({...commandForm, timeout: parseFloat(e.target.value)})}
                  inputProps={{ step: 0.5, min: 1, max: 120 }}
                />
              </Grid>
            </Grid>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCommandDialogOpen(false)}>取消</Button>
            <Button onClick={handleSendCommand} variant="contained">发送命令</Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default RobotControlPanel;
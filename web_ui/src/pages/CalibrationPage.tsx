import React, { useState, useEffect } from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Alert,
  LinearProgress,
  IconButton,
  Tooltip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  FormControl,
  FormLabel,
  TextField,
  Switch,
  FormControlLabel,
  Chip,
} from '@mui/material';
import {
  CameraAlt as CameraIcon,
  SmartToy as RobotIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Settings as SettingsIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
  Visibility as VisionIcon,
  PrecisionManufacturing as PrecisionIcon,
  GridOn as GridIcon,
} from '@mui/icons-material';

import { useWebSocket } from '../context/WebSocketContext';

interface CalibrationStep {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  required: boolean;
}

interface CalibrationData {
  camera_matrix: number[][] | null;
  distortion_coeffs: number[] | null;
  robot_transform: number[][] | null;
  board_corners: number[][] | null;
  accuracy_score: number;
  timestamp: number;
}

const CalibrationPage: React.FC = () => {
  const { connectSystem, onSystemMessage, systemConnected } = useWebSocket();
  const [activeStep, setActiveStep] = useState(0);
  const [calibrationInProgress, setCalibrationInProgress] = useState(false);
  const [calibrationData, setCalibrationData] = useState<CalibrationData>({
    camera_matrix: null,
    distortion_coeffs: null,
    robot_transform: null,
    board_corners: null,
    accuracy_score: 0,
    timestamp: 0,
  });
  const [progress, setProgress] = useState(0);
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(true);
  const [autoCapture, setAutoCapture] = useState(true);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);

  const calibrationSteps: CalibrationStep[] = [
    {
      id: 'camera_intrinsic',
      title: '相机内参标定',
      description: '使用标定板标定相机的内参数矩阵和畸变系数',
      status: 'pending',
      required: true,
    },
    {
      id: 'robot_workspace',
      title: '机器人工作空间标定',
      description: '标定机械臂的工作空间和关节限制',
      status: 'pending',
      required: true,
    },
    {
      id: 'hand_eye_calibration',
      title: '手眼标定',
      description: '标定相机与机械臂末端执行器之间的变换关系',
      status: 'pending',
      required: true,
    },
    {
      id: 'board_detection',
      title: '棋盘检测标定',
      description: '标定棋盘在相机视野中的位置和尺寸',
      status: 'pending',
      required: true,
    },
    {
      id: 'accuracy_validation',
      title: '精度验证',
      description: '验证整体标定精度和系统性能',
      status: 'pending',
      required: false,
    },
  ];

  const [steps, setSteps] = useState(calibrationSteps);

  useEffect(() => {
    connectSystem();

    const unsubscribe = onSystemMessage((message) => {
      switch (message.type) {
        case 'calibration_progress':
          setProgress(message.data.progress);
          setCurrentImage(message.data.current_image);
          break;
        case 'calibration_step_complete':
          updateStepStatus(message.data.step_id, 'completed');
          setCalibrationData(prev => ({
            ...prev,
            ...message.data.results,
          }));
          break;
        case 'calibration_error':
          updateStepStatus(message.data.step_id, 'error');
          break;
        case 'calibration_complete':
          setCalibrationInProgress(false);
          setCalibrationData(message.data.results);
          break;
        default:
          break;
      }
    });

    // 加载已保存的标定数据
    loadCalibrationData();

    return () => {
      unsubscribe();
    };
  }, []);

  const updateStepStatus = (stepId: string, status: CalibrationStep['status']) => {
    setSteps(prev => prev.map(step =>
      step.id === stepId ? { ...step, status } : step
    ));
  };

  const loadCalibrationData = async () => {
    try {
      const response = await fetch('/api/v1/calibration/data');
      if (response.ok) {
        const data = await response.json();
        setCalibrationData(data);

        // 更新步骤状态
        if (data.camera_matrix) updateStepStatus('camera_intrinsic', 'completed');
        if (data.robot_transform) updateStepStatus('robot_workspace', 'completed');
        if (data.board_corners) updateStepStatus('board_detection', 'completed');
      }
    } catch (error) {
      console.error('Failed to load calibration data:', error);
    }
  };

  const startCalibrationStep = async (stepId: string) => {
    try {
      setCalibrationInProgress(true);
      updateStepStatus(stepId, 'in_progress');

      const response = await fetch(`/api/v1/calibration/start/${stepId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          auto_capture: autoCapture,
          preview_enabled: showPreview,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start calibration step');
      }
    } catch (error) {
      console.error('Calibration step failed:', error);
      updateStepStatus(stepId, 'error');
      setCalibrationInProgress(false);
    }
  };

  const stopCalibration = async () => {
    try {
      await fetch('/api/v1/calibration/stop', { method: 'POST' });
      setCalibrationInProgress(false);
      setSteps(prev => prev.map(step =>
        step.status === 'in_progress' ? { ...step, status: 'pending' } : step
      ));
    } catch (error) {
      console.error('Failed to stop calibration:', error);
    }
  };

  const saveCalibration = async () => {
    try {
      const response = await fetch('/api/v1/calibration/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(calibrationData),
      });

      if (response.ok) {
        setSaveDialogOpen(false);
        // 显示成功消息
      }
    } catch (error) {
      console.error('Failed to save calibration:', error);
    }
  };

  const resetCalibration = async () => {
    try {
      await fetch('/api/v1/calibration/reset', { method: 'POST' });
      setSteps(calibrationSteps);
      setCalibrationData({
        camera_matrix: null,
        distortion_coeffs: null,
        robot_transform: null,
        board_corners: null,
        accuracy_score: 0,
        timestamp: 0,
      });
      setActiveStep(0);
    } catch (error) {
      console.error('Failed to reset calibration:', error);
    }
  };

  const getStepIcon = (step: CalibrationStep) => {
    switch (step.status) {
      case 'completed':
        return <CheckIcon color="success" />;
      case 'error':
        return <ErrorIcon color="error" />;
      case 'in_progress':
        return <LinearProgress sx={{ width: 20 }} />;
      default:
        return step.id === 'camera_intrinsic' ? <CameraIcon /> :
               step.id === 'robot_workspace' ? <RobotIcon /> :
               step.id === 'hand_eye_calibration' ? <PrecisionIcon /> :
               step.id === 'board_detection' ? <GridIcon /> :
               <VisionIcon />;
    }
  };

  const getStepColor = (step: CalibrationStep) => {
    switch (step.status) {
      case 'completed':
        return 'success';
      case 'error':
        return 'error';
      case 'in_progress':
        return 'primary';
      default:
        return 'default';
    }
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* 页面标题 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" component="h1" fontWeight={600}>
          硬件标定
        </Typography>
        <Box>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={resetCalibration}
            disabled={calibrationInProgress}
            sx={{ mr: 1 }}
          >
            重置
          </Button>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={() => setSaveDialogOpen(true)}
            disabled={calibrationData.accuracy_score === 0}
          >
            保存标定
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* 标定步骤 */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              标定流程
            </Typography>

            <Stepper activeStep={activeStep} orientation="vertical">
              {steps.map((step, index) => (
                <Step key={step.id} completed={step.status === 'completed'}>
                  <StepLabel
                    optional={!step.required && <Typography variant="caption">可选</Typography>}
                    error={step.status === 'error'}
                    icon={getStepIcon(step)}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {step.title}
                      <Chip
                        label={step.status === 'pending' ? '待执行' :
                               step.status === 'in_progress' ? '进行中' :
                               step.status === 'completed' ? '已完成' : '错误'}
                        color={getStepColor(step)}
                        size="small"
                      />
                    </Box>
                  </StepLabel>
                  <StepContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {step.description}
                    </Typography>

                    {step.status === 'in_progress' && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          进度: {progress.toFixed(1)}%
                        </Typography>
                        <LinearProgress variant="determinate" value={progress} />
                      </Box>
                    )}

                    <Box sx={{ mb: 1 }}>
                      {step.status === 'pending' || step.status === 'error' ? (
                        <Button
                          variant="contained"
                          size="small"
                          startIcon={<PlayIcon />}
                          onClick={() => startCalibrationStep(step.id)}
                          disabled={calibrationInProgress}
                        >
                          开始标定
                        </Button>
                      ) : step.status === 'in_progress' ? (
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<StopIcon />}
                          onClick={stopCalibration}
                        >
                          停止标定
                        </Button>
                      ) : (
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<RefreshIcon />}
                          onClick={() => startCalibrationStep(step.id)}
                          disabled={calibrationInProgress}
                        >
                          重新标定
                        </Button>
                      )}

                      {index < steps.length - 1 && (
                        <Button
                          size="small"
                          onClick={() => setActiveStep(index + 1)}
                          sx={{ ml: 1 }}
                        >
                          下一步
                        </Button>
                      )}
                    </Box>
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          </Paper>
        </Grid>

        {/* 实时预览和设置 */}
        <Grid item xs={12} lg={4}>
          <Grid container spacing={2}>
            {/* 实时预览 */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    实时预览
                  </Typography>

                  <Box sx={{
                    width: '100%',
                    height: 240,
                    backgroundColor: 'grey.100',
                    border: '2px dashed',
                    borderColor: 'grey.300',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mb: 2
                  }}>
                    {currentImage ? (
                      <img
                        src={currentImage}
                        alt="标定预览"
                        style={{
                          maxWidth: '100%',
                          maxHeight: '100%',
                          objectFit: 'contain'
                        }}
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        {systemConnected ? '等待图像数据...' : '未连接到系统'}
                      </Typography>
                    )}
                  </Box>

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={showPreview}
                          onChange={(e) => setShowPreview(e.target.checked)}
                        />
                      }
                      label="显示预览"
                    />
                    <IconButton onClick={() => window.location.reload()}>
                      <RefreshIcon />
                    </IconButton>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* 标定设置 */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    标定设置
                  </Typography>

                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={autoCapture}
                          onChange={(e) => setAutoCapture(e.target.checked)}
                        />
                      }
                      label="自动捕获图像"
                    />

                    <FormControl>
                      <FormLabel>标定板尺寸</FormLabel>
                      <TextField
                        size="small"
                        defaultValue="9x6"
                        helperText="格式: 宽x高 (角点数量)"
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>方格大小 (mm)</FormLabel>
                      <TextField
                        size="small"
                        type="number"
                        defaultValue={20}
                        helperText="标定板方格的实际大小"
                      />
                    </FormControl>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* 标定结果 */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    标定结果
                  </Typography>

                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <CameraIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="相机标定"
                        secondary={calibrationData.camera_matrix ? '已完成' : '未完成'}
                      />
                      {calibrationData.camera_matrix && <CheckIcon color="success" />}
                    </ListItem>

                    <ListItem>
                      <ListItemIcon>
                        <RobotIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="机器人标定"
                        secondary={calibrationData.robot_transform ? '已完成' : '未完成'}
                      />
                      {calibrationData.robot_transform && <CheckIcon color="success" />}
                    </ListItem>

                    <ListItem>
                      <ListItemIcon>
                        <GridIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="棋盘检测"
                        secondary={calibrationData.board_corners ? '已完成' : '未完成'}
                      />
                      {calibrationData.board_corners && <CheckIcon color="success" />}
                    </ListItem>

                    <Divider sx={{ my: 1 }} />

                    <ListItem>
                      <ListItemText
                        primary="整体精度"
                        secondary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={calibrationData.accuracy_score * 100}
                              sx={{ flexGrow: 1 }}
                            />
                            <Typography variant="body2">
                              {(calibrationData.accuracy_score * 100).toFixed(1)}%
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                  </List>

                  {calibrationData.timestamp > 0 && (
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                      最后更新: {new Date(calibrationData.timestamp).toLocaleString()}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Grid>
      </Grid>

      {/* 保存对话框 */}
      <Dialog open={saveDialogOpen} onClose={() => setSaveDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>保存标定数据</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            保存标定数据后，系统将使用这些参数进行后续的视觉识别和机器人控制。
          </Alert>

          <Typography variant="body2" sx={{ mb: 2 }}>
            标定概要:
          </Typography>

          <List dense>
            <ListItem>
              <ListItemText primary="相机内参" secondary={calibrationData.camera_matrix ? '✓ 已标定' : '✗ 未标定'} />
            </ListItem>
            <ListItem>
              <ListItemText primary="机器人变换" secondary={calibrationData.robot_transform ? '✓ 已标定' : '✗ 未标定'} />
            </ListItem>
            <ListItem>
              <ListItemText primary="棋盘检测" secondary={calibrationData.board_corners ? '✓ 已标定' : '✗ 未标定'} />
            </ListItem>
            <ListItem>
              <ListItemText primary="精度评分" secondary={`${(calibrationData.accuracy_score * 100).toFixed(1)}%`} />
            </ListItem>
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveDialogOpen(false)}>
            取消
          </Button>
          <Button onClick={saveCalibration} variant="contained">
            保存
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default CalibrationPage;
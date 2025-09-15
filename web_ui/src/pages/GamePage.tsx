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
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Slider,
  Switch,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Psychology as AIIcon,
  Person as PersonIcon,
  History as HistoryIcon,
} from '@mui/icons-material';

import ChessBoard from '../components/Chess/ChessBoard';
import ChessBoard3D from '../components/Chess/ChessBoard3D';
import { useGame } from '../context/GameContext';
import { useWebSocket } from '../context/WebSocketContext';

const GamePage: React.FC = () => {
  const {
    state: gameState,
    createGame,
    startGame,
    makeMove,
    pauseGame,
    endGame,
    setAIDifficulty,
    resetGame,
  } = useGame();

  const { connect, disconnect, onMessage, status: wsStatus } = useWebSocket();

  const [newGameDialogOpen, setNewGameDialogOpen] = useState(false);
  const [selectedColor, setSelectedColor] = useState<'white' | 'black'>('white');
  const [selectedDifficulty, setSelectedDifficulty] = useState(3);
  const [moveHistory, setMoveHistory] = useState<Array<{move: string, player: string, timestamp: number}>>([]);
  const [is3DMode, setIs3DMode] = useState(false);

  // WebSocket消息处理
  useEffect(() => {
    if (gameState.gameId) {
      connect(gameState.gameId);

      const unsubscribe = onMessage((message) => {
        switch (message.type) {
          case 'move_broadcast':
            console.log('Move received:', message.data);
            break;
          case 'ai_move_result':
            console.log('AI move:', message.data);
            if (message.data.analysis?.best_move) {
              handleAIMove(message.data.analysis.best_move);
            }
            break;
          case 'game_status':
            console.log('Game status:', message.data);
            break;
          default:
            console.log('Unknown message:', message);
        }
      });

      return () => {
        unsubscribe();
        disconnect();
      };
    }
  }, [gameState.gameId]);

  // 处理AI移动
  const handleAIMove = (move: string) => {
    setMoveHistory(prev => [...prev, {
      move,
      player: 'AI',
      timestamp: Date.now()
    }]);
  };

  // 处理玩家移动
  const handlePlayerMove = async (move: string) => {
    if (gameState.status !== 'playing') return;
    if (gameState.currentPlayer !== gameState.humanColor) return;

    try {
      await makeMove(move, 'human');
      setMoveHistory(prev => [...prev, {
        move,
        player: '玩家',
        timestamp: Date.now()
      }]);
    } catch (error) {
      console.error('Move failed:', error);
    }
  };

  // 创建新游戏
  const handleCreateGame = async () => {
    try {
      await createGame(selectedColor, selectedDifficulty);
      setNewGameDialogOpen(false);
      setMoveHistory([]);
    } catch (error) {
      console.error('Failed to create game:', error);
    }
  };

  // 开始游戏
  const handleStartGame = async () => {
    try {
      await startGame();
    } catch (error) {
      console.error('Failed to start game:', error);
    }
  };

  // 暂停游戏
  const handlePauseGame = async () => {
    try {
      await pauseGame();
    } catch (error) {
      console.error('Failed to pause game:', error);
    }
  };

  // 结束游戏
  const handleEndGame = async () => {
    try {
      await endGame();
      setMoveHistory([]);
    } catch (error) {
      console.error('Failed to end game:', error);
    }
  };

  // 重置游戏
  const handleResetGame = () => {
    resetGame();
    setMoveHistory([]);
    disconnect();
  };

  // 获取状态显示文本
  const getStatusText = (status: string) => {
    switch (status) {
      case 'waiting':
        return '等待开始';
      case 'playing':
        return '游戏进行中';
      case 'paused':
        return '已暂停';
      case 'finished':
        return '游戏结束';
      default:
        return '未知状态';
    }
  };

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'playing':
        return 'success';
      case 'paused':
        return 'warning';
      case 'finished':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* 页面标题 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" component="h1" fontWeight={600}>
          象棋对弈
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FormControlLabel
            control={
              <Switch
                checked={is3DMode}
                onChange={(_e, checked) => setIs3DMode(checked)}
              />
            }
            label="3D模式"
          />
          <Button
            variant="contained"
            startIcon={<PlayIcon />}
            onClick={() => setNewGameDialogOpen(true)}
            sx={{ mr: 1 }}
          >
            新游戏
          </Button>
          <Tooltip title="刷新">
            <IconButton onClick={() => window.location.reload()}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* 棋盘区域 */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            {/* 游戏状态栏 */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, width: '100%' }}>
              <Chip
                label={getStatusText(gameState.status)}
                color={getStatusColor(gameState.status)}
                icon={gameState.status === 'playing' ? <PlayIcon /> : undefined}
              />

              {gameState.status === 'playing' && (
                <Chip
                  label={`当前: ${gameState.currentPlayer === 'white' ? '白方' : '黑方'}`}
                  color={gameState.currentPlayer === 'white' ? 'default' : 'secondary'}
                  icon={gameState.currentPlayer === gameState.humanColor ? <PersonIcon /> : <AIIcon />}
                />
              )}

              <Chip
                label={`连接: ${wsStatus === 'connected' ? '已连接' : '未连接'}`}
                color={wsStatus === 'connected' ? 'success' : 'error'}
                size="small"
              />

              {gameState.isLoading && (
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <CircularProgress size={20} />
                  <Typography variant="caption" sx={{ ml: 1 }}>
                    处理中...
                  </Typography>
                </Box>
              )}
            </Box>

            {/* 错误提示 */}
            {gameState.error && (
              <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
                {gameState.error}
              </Alert>
            )}

            {/* 棋盘 */}
            {is3DMode ? (
              <ChessBoard3D
                fen={gameState.boardFen}
                onMove={handlePlayerMove}
                interactive={gameState.status === 'playing' && gameState.currentPlayer === gameState.humanColor}
                orientation={gameState.humanColor}
                size={Math.min(500, window.innerWidth - 100)}
                lastMove={gameState.lastMove || undefined}
              />
            ) : (
              <ChessBoard
                fen={gameState.boardFen}
                onMove={handlePlayerMove}
                interactive={gameState.status === 'playing' && gameState.currentPlayer === gameState.humanColor}
                orientation={gameState.humanColor}
                size={Math.min(500, window.innerWidth - 100)}
                lastMove={gameState.lastMove || undefined}
              />
            )}

            {/* 游戏控制按钮 */}
            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              {gameState.status === 'waiting' && gameState.gameId && (
                <Button
                  variant="contained"
                  startIcon={<PlayIcon />}
                  onClick={handleStartGame}
                  disabled={gameState.isLoading}
                >
                  开始游戏
                </Button>
              )}

              {gameState.status === 'playing' && (
                <Button
                  variant="outlined"
                  startIcon={<PauseIcon />}
                  onClick={handlePauseGame}
                  disabled={gameState.isLoading}
                >
                  暂停
                </Button>
              )}

              {gameState.status === 'paused' && (
                <Button
                  variant="contained"
                  startIcon={<PlayIcon />}
                  onClick={handleStartGame}
                  disabled={gameState.isLoading}
                >
                  继续
                </Button>
              )}

              {(gameState.status === 'playing' || gameState.status === 'paused') && (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={handleEndGame}
                  disabled={gameState.isLoading}
                >
                  结束游戏
                </Button>
              )}

              <Button
                variant="outlined"
                onClick={handleResetGame}
                disabled={gameState.isLoading}
              >
                重置
              </Button>
            </Box>
          </Paper>
        </Grid>

        {/* 侧边信息栏 */}
        <Grid item xs={12} lg={4}>
          <Grid container spacing={2}>
            {/* 游戏信息 */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    游戏信息
                  </Typography>
                  <Divider sx={{ my: 1 }} />

                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">游戏ID:</Typography>
                      <Typography variant="body2" fontWeight={500}>
                        {gameState.gameId ? gameState.gameId.slice(0, 8) + '...' : '无'}
                      </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">玩家颜色:</Typography>
                      <Chip
                        label={gameState.humanColor === 'white' ? '白方' : '黑方'}
                        color={gameState.humanColor === 'white' ? 'default' : 'secondary'}
                        size="small"
                      />
                    </Box>

                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">AI难度:</Typography>
                      <Typography variant="body2" fontWeight={500}>
                        {gameState.aiDifficulty} 级
                      </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">移动次数:</Typography>
                      <Typography variant="body2" fontWeight={500}>
                        {gameState.moveHistory.length}
                      </Typography>
                    </Box>
                  </Box>

                  {gameState.gameId && (
                    <Box sx={{ mt: 2 }}>
                      <Button
                        variant="outlined"
                        startIcon={<SettingsIcon />}
                        size="small"
                        fullWidth
                        onClick={() => {
                          // 打开设置对话框
                        }}
                      >
                        游戏设置
                      </Button>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* 移动历史 */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <HistoryIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                    移动历史
                  </Typography>
                  <Divider sx={{ my: 1 }} />

                  <List sx={{ maxHeight: 300, overflow: 'auto' }}>
                    {moveHistory.length === 0 ? (
                      <ListItem>
                        <ListItemText
                          primary="暂无移动记录"
                          primaryTypographyProps={{
                            variant: 'body2',
                            color: 'text.secondary',
                            textAlign: 'center'
                          }}
                        />
                      </ListItem>
                    ) : (
                      moveHistory.map((move, index) => (
                        <ListItem key={index} dense>
                          <ListItemText
                            primary={`${index + 1}. ${move.move}`}
                            secondary={`${move.player} - ${new Date(move.timestamp).toLocaleTimeString()}`}
                            primaryTypographyProps={{ variant: 'body2' }}
                            secondaryTypographyProps={{ variant: 'caption' }}
                          />
                        </ListItem>
                      ))
                    )}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Grid>
      </Grid>

      {/* 新游戏对话框 */}
      <Dialog open={newGameDialogOpen} onClose={() => setNewGameDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>创建新游戏</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <FormControl component="fieldset" sx={{ mb: 3 }}>
              <FormLabel component="legend">选择颜色</FormLabel>
              <RadioGroup
                value={selectedColor}
                onChange={(e) => setSelectedColor(e.target.value as 'white' | 'black')}
                row
              >
                <FormControlLabel value="white" control={<Radio />} label="白方（先手）" />
                <FormControlLabel value="black" control={<Radio />} label="黑方（后手）" />
              </RadioGroup>
            </FormControl>

            <Box sx={{ mb: 3 }}>
              <Typography gutterBottom>AI难度: {selectedDifficulty} 级</Typography>
              <Slider
                value={selectedDifficulty}
                onChange={(_, value) => setSelectedDifficulty(value as number)}
                min={1}
                max={10}
                marks={[
                  { value: 1, label: '初学' },
                  { value: 5, label: '中级' },
                  { value: 10, label: '大师' },
                ]}
                valueLabelDisplay="auto"
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewGameDialogOpen(false)}>
            取消
          </Button>
          <Button onClick={handleCreateGame} variant="contained">
            创建游戏
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default GamePage;
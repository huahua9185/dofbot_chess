import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Chip,
  Badge,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Notifications as NotificationsIcon,
  Settings as SettingsIcon,
  AccountCircle,
} from '@mui/icons-material';

import { useWebSocket } from '../../context/WebSocketContext';

interface NavbarProps {
  onMenuClick: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onMenuClick }) => {
  const { status, systemConnected } = useWebSocket();

  const getConnectionStatusColor = () => {
    switch (status) {
      case 'connected':
        return 'success';
      case 'connecting':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getConnectionStatusText = () => {
    switch (status) {
      case 'connected':
        return '已连接';
      case 'connecting':
        return '连接中';
      case 'disconnected':
        return '已断开';
      case 'error':
        return '连接错误';
      default:
        return '未知';
    }
  };

  return (
    <AppBar
      position="fixed"
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        backgroundColor: '#1976d2',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      }}
    >
      <Toolbar>
        <IconButton
          color="inherit"
          edge="start"
          onClick={onMenuClick}
          sx={{ mr: 2 }}
        >
          <MenuIcon />
        </IconButton>

        <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
          智能象棋机器人
        </Typography>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* 连接状态指示器 */}
          <Chip
            label={`游戏: ${getConnectionStatusText()}`}
            color={getConnectionStatusColor()}
            size="small"
            variant="outlined"
            sx={{
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              color: 'white',
              borderColor: 'rgba(255, 255, 255, 0.3)',
              '& .MuiChip-label': {
                fontSize: '0.75rem',
              },
            }}
          />

          <Chip
            label={`系统: ${systemConnected ? '已连接' : '未连接'}`}
            color={systemConnected ? 'success' : 'default'}
            size="small"
            variant="outlined"
            sx={{
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              color: 'white',
              borderColor: 'rgba(255, 255, 255, 0.3)',
              '& .MuiChip-label': {
                fontSize: '0.75rem',
              },
            }}
          />

          {/* 通知按钮 */}
          <IconButton color="inherit" size="small">
            <Badge badgeContent={0} color="error">
              <NotificationsIcon />
            </Badge>
          </IconButton>

          {/* 设置按钮 */}
          <IconButton color="inherit" size="small">
            <SettingsIcon />
          </IconButton>

          {/* 用户菜单 */}
          <IconButton color="inherit" size="small">
            <AccountCircle />
          </IconButton>
        </div>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
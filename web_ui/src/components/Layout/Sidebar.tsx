import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Box,
  Typography,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  SportsEsports as GameIcon,
  Computer as SystemIcon,
  Settings as CalibrationIcon,
  Analytics as AnalyticsIcon,
  Memory as MemoryIcon,
  Visibility as VisionIcon,
  SmartToy as RobotIcon,
} from '@mui/icons-material';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ open, onClose }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      text: '仪表板',
      icon: <DashboardIcon />,
      path: '/dashboard',
      description: '系统概览',
    },
    {
      text: '游戏界面',
      icon: <GameIcon />,
      path: '/game',
      description: '开始对弈',
    },
    {
      text: '系统监控',
      icon: <SystemIcon />,
      path: '/system',
      description: '性能监控',
    },
    {
      text: '硬件标定',
      icon: <CalibrationIcon />,
      path: '/calibration',
      description: '设备校准',
    },
  ];

  const statusItems = [
    {
      text: 'AI引擎',
      icon: <MemoryIcon />,
      status: 'running',
    },
    {
      text: '视觉系统',
      icon: <VisionIcon />,
      status: 'running',
    },
    {
      text: '机器人',
      icon: <RobotIcon />,
      status: 'connected',
    },
  ];

  const handleNavigation = (path: string) => {
    navigate(path);
    onClose();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
      case 'connected':
        return '#4caf50';
      case 'warning':
        return '#ff9800';
      case 'error':
        return '#f44336';
      default:
        return '#9e9e9e';
    }
  };

  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      sx={{
        '& .MuiDrawer-paper': {
          width: 280,
          boxSizing: 'border-box',
          mt: 8, // 为Navbar留出空间
          height: 'calc(100% - 64px)',
        },
      }}
    >
      <Box sx={{ overflow: 'auto' }}>
        {/* 导航菜单 */}
        <Box sx={{ p: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, fontWeight: 600 }}>
            导航菜单
          </Typography>
        </Box>

        <List>
          {menuItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => handleNavigation(item.path)}
                sx={{
                  mx: 1,
                  mb: 0.5,
                  borderRadius: 2,
                  '&.Mui-selected': {
                    backgroundColor: 'primary.main',
                    color: 'primary.contrastText',
                    '& .MuiListItemIcon-root': {
                      color: 'primary.contrastText',
                    },
                  },
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: 40,
                    color: location.pathname === item.path ? 'inherit' : 'action.active',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  secondary={item.description}
                  primaryTypographyProps={{
                    fontSize: '0.9rem',
                    fontWeight: location.pathname === item.path ? 600 : 400,
                  }}
                  secondaryTypographyProps={{
                    fontSize: '0.75rem',
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ my: 2 }} />

        {/* 系统状态 */}
        <Box sx={{ p: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, fontWeight: 600 }}>
            系统状态
          </Typography>
        </Box>

        <List>
          {statusItems.map((item) => (
            <ListItem key={item.text} disablePadding>
              <ListItemButton sx={{ mx: 1, borderRadius: 2 }}>
                <ListItemIcon sx={{ minWidth: 40 }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    fontSize: '0.85rem',
                  }}
                />
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: getStatusColor(item.status),
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider sx={{ my: 2 }} />

        {/* 快捷操作 */}
        <Box sx={{ p: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, fontWeight: 600 }}>
            快捷操作
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <ListItemButton
              sx={{
                borderRadius: 2,
                backgroundColor: 'success.main',
                color: 'success.contrastText',
                '&:hover': {
                  backgroundColor: 'success.dark',
                },
              }}
              onClick={() => handleNavigation('/game')}
            >
              <ListItemIcon sx={{ minWidth: 40, color: 'inherit' }}>
                <GameIcon />
              </ListItemIcon>
              <ListItemText
                primary="开始新游戏"
                primaryTypographyProps={{
                  fontSize: '0.85rem',
                  fontWeight: 500,
                }}
              />
            </ListItemButton>

            <ListItemButton
              sx={{
                borderRadius: 2,
                backgroundColor: 'warning.main',
                color: 'warning.contrastText',
                '&:hover': {
                  backgroundColor: 'warning.dark',
                },
              }}
              onClick={() => {
                // 紧急停止逻辑
                console.log('Emergency stop triggered');
              }}
            >
              <ListItemIcon sx={{ minWidth: 40, color: 'inherit' }}>
                <RobotIcon />
              </ListItemIcon>
              <ListItemText
                primary="紧急停止"
                primaryTypographyProps={{
                  fontSize: '0.85rem',
                  fontWeight: 500,
                }}
              />
            </ListItemButton>
          </Box>
        </Box>
      </Box>
    </Drawer>
  );
};

export default Sidebar;
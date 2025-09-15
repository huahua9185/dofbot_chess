import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box } from '@mui/material';

import Navbar from './components/Layout/Navbar';
import Sidebar from './components/Layout/Sidebar';
import GamePage from './pages/GamePage';
import DashboardPage from './pages/DashboardPage';
import SystemPage from './pages/SystemPage';
import CalibrationPage from './pages/CalibrationPage';

import { GameProvider } from './context/GameContext';
import { WebSocketProvider } from './context/WebSocketContext';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    fontFamily: 'Roboto, Arial, sans-serif',
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 500,
    },
  },
  components: {
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#fff',
          borderRight: '1px solid #e0e0e0',
        },
      },
    },
  },
});

const App: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  const handleSidebarToggle = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <WebSocketProvider>
        <GameProvider>
          <Router>
            <Box sx={{ display: 'flex' }}>
              <Navbar onMenuClick={handleSidebarToggle} />
              <Sidebar
                open={sidebarOpen}
                onClose={() => setSidebarOpen(false)}
              />

              <Box
                component="main"
                sx={{
                  flexGrow: 1,
                  minHeight: '100vh',
                  pt: 8, // 为Navbar留出空间
                  backgroundColor: 'background.default',
                }}
              >
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/game" element={<GamePage />} />
                  <Route path="/system" element={<SystemPage />} />
                  <Route path="/calibration" element={<CalibrationPage />} />
                </Routes>
              </Box>
            </Box>
          </Router>
        </GameProvider>
      </WebSocketProvider>
    </ThemeProvider>
  );
};

export default App;
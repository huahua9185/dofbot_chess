import React, { useRef, useState, useEffect, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Box } from '@react-three/drei';
import { Chess, Square } from 'chess.js';
import * as THREE from 'three';
import { Box as MuiBox, Switch, FormControlLabel, Slider, Typography } from '@mui/material';

interface ChessBoard3DProps {
  fen?: string;
  onMove?: (move: string) => void;
  interactive?: boolean;
  orientation?: 'white' | 'black';
  size?: number;
  showCoordinates?: boolean;
  highlightLastMove?: boolean;
  lastMove?: string;
}

// 3D棋子组件
const ChessPiece3D: React.FC<{
  piece: string;
  position: [number, number, number];
  onClick?: () => void;
  isSelected?: boolean;
}> = ({ piece, position, onClick, isSelected }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += isSelected ? 0.02 : 0;
    }
  });

  // 根据棋子类型选择几何体
  const pieceGeometry = useMemo(() => {
    const type = piece.toLowerCase();
    switch (type) {
      case 'k': return new THREE.ConeGeometry(0.3, 0.8, 8); // 王
      case 'q': return new THREE.ConeGeometry(0.25, 0.7, 8); // 后
      case 'r': return new THREE.BoxGeometry(0.4, 0.6, 0.4); // 车
      case 'b': return new THREE.ConeGeometry(0.2, 0.6, 6); // 象
      case 'n': return new THREE.BoxGeometry(0.3, 0.5, 0.3); // 马
      case 'p': return new THREE.SphereGeometry(0.2, 8, 6); // 兵
      default: return new THREE.SphereGeometry(0.2, 8, 6);
    }
  }, [piece]);

  const material = useMemo(() => {
    const color = piece[0] === 'w' ? '#f0f0f0' : '#333333';
    return new THREE.MeshPhongMaterial({
      color,
      shininess: 100,
      transparent: true,
      opacity: hovered ? 0.8 : 1.0
    });
  }, [piece, hovered]);

  return (
    <mesh
      ref={meshRef}
      position={position}
      geometry={pieceGeometry}
      material={material}
      onClick={onClick}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
      castShadow
      receiveShadow
    />
  );
};

// 3D方格组件
const ChessSquare3D: React.FC<{
  position: [number, number, number];
  isLight: boolean;
  isSelected?: boolean;
  isPossibleMove?: boolean;
  isLastMove?: boolean;
  onClick?: () => void;
}> = ({ position, isLight, isSelected, isPossibleMove, isLastMove, onClick }) => {
  const [hovered, setHovered] = useState(false);

  const squareColor = useMemo(() => {
    if (isSelected) return '#ffeb3b';
    if (isLastMove) return '#4caf50';
    if (isPossibleMove) return '#2196f3';
    return isLight ? '#f0d9b5' : '#b58863';
  }, [isLight, isSelected, isPossibleMove, isLastMove]);

  return (
    <Box
      position={position}
      args={[0.9, 0.1, 0.9]}
      onClick={onClick}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      <meshPhongMaterial color={squareColor} />
    </Box>
  );
};

const ChessBoard3D: React.FC<ChessBoard3DProps> = ({
  fen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  onMove,
  interactive = true,
  orientation = 'white',
  size = 400,
  showCoordinates = true,
  highlightLastMove = true,
  lastMove,
}) => {
  const [game, setGame] = useState<Chess>(() => new Chess(fen));
  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [possibleMoves, setPossibleMoves] = useState<string[]>([]);
  const [cameraPosition, setCameraPosition] = useState<[number, number, number]>([6, 8, 6]);
  const [enableControls, setEnableControls] = useState(true);

  // 更新棋盘状态
  useEffect(() => {
    try {
      const newGame = new Chess(fen);
      setGame(newGame);
      setSelectedSquare(null);
      setPossibleMoves([]);
    } catch (error) {
      console.error('Invalid FEN:', error);
    }
  }, [fen]);

  // 3D场景设置
  const SceneSetup: React.FC = () => {
    return (
      <>
        {/* 环境光 */}
        <ambientLight intensity={0.4} />

        {/* 方向光 */}
        <directionalLight
          position={[10, 10, 5]}
          intensity={1}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-far={50}
          shadow-camera-left={-10}
          shadow-camera-right={10}
          shadow-camera-top={10}
          shadow-camera-bottom={-10}
        />

        {/* 棋盘边框 */}
        <Box position={[0, -0.2, 0]} args={[9, 0.3, 9]}>
          <meshPhongMaterial color="#8b4513" />
        </Box>

        {/* 方格和棋子 */}
        {renderBoard()}

        {/* 坐标系 */}
        {showCoordinates && renderCoordinates()}
      </>
    );
  };

  // 获取方格颜色
  const getSquareColor = (file: number, rank: number): boolean => {
    return (file + rank) % 2 === 0;
  };

  // 获取方格名称
  const getSquareName = (file: number, rank: number): Square => {
    const files = 'abcdefgh';
    const actualFile = orientation === 'white' ? file : 7 - file;
    const actualRank = orientation === 'white' ? 7 - rank : rank;
    return `${files[actualFile]}${actualRank + 1}` as Square;
  };

  // 获取3D位置
  const getPosition3D = (file: number, rank: number, height = 0): [number, number, number] => {
    const x = (file - 3.5);
    const z = (rank - 3.5);
    return [x, height, z];
  };

  // 处理方格点击
  const handleSquareClick = (square: Square) => {
    if (!interactive) return;

    const piece = game.get(square);

    if (selectedSquare === null) {
      // 选择棋子
      if (piece && piece.color === game.turn()) {
        setSelectedSquare(square);
        const moves = game.moves({ square, verbose: true });
        setPossibleMoves(moves.map((move: any) => move.to));
      }
    } else {
      // 执行移动或重新选择
      if (selectedSquare === square) {
        // 取消选择
        setSelectedSquare(null);
        setPossibleMoves([]);
      } else if (piece && piece.color === game.turn()) {
        // 选择新棋子
        setSelectedSquare(square);
        const moves = game.moves({ square, verbose: true });
        setPossibleMoves(moves.map((move: any) => move.to));
      } else {
        // 尝试移动
        const moveString = `${selectedSquare}${square}`;
        const move = game.move({
          from: selectedSquare,
          to: square,
          promotion: 'q', // 默认升变为皇后
        });

        if (move) {
          setGame(new Chess(game.fen()));
          setSelectedSquare(null);
          setPossibleMoves([]);

          if (onMove) {
            onMove(moveString);
          }
        } else {
          // 无效移动，取消选择
          setSelectedSquare(null);
          setPossibleMoves([]);
        }
      }
    }
  };

  // 检查方格状态
  const getSquareState = (square: Square) => {
    return {
      isSelected: selectedSquare === square,
      isPossibleMove: possibleMoves.includes(square),
      isLastMove: !!(highlightLastMove && lastMove && lastMove.includes(square)),
    };
  };

  // 渲染棋盘
  const renderBoard = () => {
    const squares = [];
    const pieces = [];

    for (let rank = 0; rank < 8; rank++) {
      for (let file = 0; file < 8; file++) {
        const square = getSquareName(file, rank);
        const piece = game.get(square);
        const position3D = getPosition3D(file, rank);
        const piecePosition3D = getPosition3D(file, rank, 0.4);
        const isLight = getSquareColor(file, rank);
        const squareState = getSquareState(square);

        // 渲染方格
        squares.push(
          <ChessSquare3D
            key={square}
            position={position3D}
            isLight={isLight}
            onClick={() => handleSquareClick(square)}
            {...squareState}
          />
        );

        // 渲染棋子
        if (piece) {
          const pieceKey = `${piece.color}${piece.type.toUpperCase()}`;
          pieces.push(
            <ChessPiece3D
              key={`${square}-piece`}
              piece={pieceKey}
              position={piecePosition3D}
              onClick={() => handleSquareClick(square)}
              isSelected={squareState.isSelected}
            />
          );
        }
      }
    }

    return [...squares, ...pieces];
  };

  // 渲染坐标
  const renderCoordinates = () => {
    const coordinates = [];
    const files = 'abcdefgh';

    // 文件标签 (a-h)
    for (let i = 0; i < 8; i++) {
      const file = orientation === 'white' ? i : 7 - i;
      coordinates.push(
        <Text
          key={`file-${i}`}
          position={[file - 3.5, 0.5, -4.5]}
          fontSize={0.3}
          color="#666"
          anchorX="center"
          anchorY="middle"
        >
          {files[file]}
        </Text>
      );
    }

    // 等级标签 (1-8)
    for (let i = 0; i < 8; i++) {
      const rank = orientation === 'white' ? 7 - i : i;
      coordinates.push(
        <Text
          key={`rank-${i}`}
          position={[-4.5, 0.5, rank - 3.5]}
          fontSize={0.3}
          color="#666"
          anchorX="center"
          anchorY="middle"
        >
          {rank + 1}
        </Text>
      );
    }

    return coordinates;
  };

  const containerStyle = { width: size, height: size + 100 };
  const controlPanelStyle = { mb: 2, display: 'flex', gap: 2, alignItems: 'center' };

  return (
    <MuiBox sx={containerStyle}>
      {/* 控制面板 */}
      <MuiBox sx={controlPanelStyle}>
        <FormControlLabel
          control={
            <Switch
              checked={enableControls}
              onChange={(e) => setEnableControls(e.target.checked)}
            />
          }
          label="启用相机控制"
        />

        <MuiBox sx={{ minWidth: 120 }}>
          <Typography gutterBottom>相机高度</Typography>
          <Slider
            value={cameraPosition[1]}
            onChange={(_, value) => setCameraPosition([cameraPosition[0], value as number, cameraPosition[2]])}
            min={4}
            max={12}
            step={0.5}
            valueLabelDisplay="auto"
          />
        </MuiBox>
      </MuiBox>

      {/* 3D场景 */}
      <Canvas
        camera={{ position: cameraPosition, fov: 50 }}
        shadows
        style={{ height: size, background: '#f5f5f5' }}
      >
        <SceneSetup />

        {enableControls && (
          <OrbitControls
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
            minDistance={5}
            maxDistance={20}
          />
        )}
      </Canvas>
    </MuiBox>
  );
};

export default ChessBoard3D;
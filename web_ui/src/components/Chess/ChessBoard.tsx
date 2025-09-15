import React, { useState, useEffect } from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { Chess, Square } from 'chess.js';

interface ChessBoardProps {
  fen?: string;
  onMove?: (move: string) => void;
  interactive?: boolean;
  orientation?: 'white' | 'black';
  size?: number;
  showCoordinates?: boolean;
  highlightLastMove?: boolean;
  lastMove?: string;
}

const ChessBoard: React.FC<ChessBoardProps> = ({
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

  const squareSize = size / 8;

  // 棋子Unicode符号映射
  const pieceSymbols: { [key: string]: string } = {
    'wK': '♔', 'wQ': '♕', 'wR': '♖', 'wB': '♗', 'wN': '♘', 'wP': '♙',
    'bK': '♚', 'bQ': '♛', 'bR': '♜', 'bB': '♝', 'bN': '♞', 'bP': '♟',
  };

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

  // 获取方格颜色
  const getSquareColor = (file: number, rank: number): 'light' | 'dark' => {
    return (file + rank) % 2 === 0 ? 'dark' : 'light';
  };

  // 获取方格名称
  const getSquareName = (file: number, rank: number): Square => {
    const files = 'abcdefgh';
    const actualFile = orientation === 'white' ? file : 7 - file;
    const actualRank = orientation === 'white' ? 7 - rank : rank;
    return `${files[actualFile]}${actualRank + 1}` as Square;
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

  // 检查方格是否被高亮
  const isSquareHighlighted = (square: Square): string => {
    if (selectedSquare === square) return 'selected';
    if (possibleMoves.includes(square)) return 'possible-move';
    if (highlightLastMove && lastMove && (lastMove.includes(square))) return 'last-move';
    return '';
  };

  // 渲染方格
  const renderSquare = (file: number, rank: number) => {
    const square = getSquareName(file, rank);
    const piece = game.get(square);
    const squareColor = getSquareColor(file, rank);
    const highlight = isSquareHighlighted(square);

    return (
      <Box
        key={square}
        sx={{
          width: squareSize,
          height: squareSize,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: interactive ? 'pointer' : 'default',
          fontSize: `${squareSize * 0.6}px`,
          fontWeight: 'bold',
          position: 'relative',
          backgroundColor: squareColor === 'light' ? '#f0d9b5' : '#b58863',
          '&:hover': interactive ? {
            opacity: 0.8,
          } : {},
          ...(highlight === 'selected' && {
            boxShadow: 'inset 0 0 0 3px #ffeb3b',
          }),
          ...(highlight === 'last-move' && {
            backgroundColor: squareColor === 'light' ? '#cdd26a' : '#aaa23a',
          }),
        }}
        onClick={() => handleSquareClick(square)}
      >
        {/* 棋子 */}
        {piece && (
          <span style={{ userSelect: 'none' }}>
            {pieceSymbols[`${piece.color}${piece.type.toUpperCase()}`]}
          </span>
        )}

        {/* 可能移动的指示点 */}
        {highlight === 'possible-move' && (
          <Box
            sx={{
              position: 'absolute',
              width: '25%',
              height: '25%',
              borderRadius: '50%',
              backgroundColor: 'rgba(76, 175, 80, 0.6)',
              pointerEvents: 'none',
            }}
          />
        )}

        {/* 坐标标签 */}
        {showCoordinates && (
          <>
            {file === (orientation === 'white' ? 0 : 7) && (
              <Typography
                sx={{
                  position: 'absolute',
                  left: 2,
                  top: 2,
                  fontSize: `${squareSize * 0.15}px`,
                  color: squareColor === 'light' ? '#b58863' : '#f0d9b5',
                  fontWeight: 'bold',
                  pointerEvents: 'none',
                }}
              >
                {orientation === 'white' ? 8 - rank : rank + 1}
              </Typography>
            )}
            {rank === (orientation === 'white' ? 7 : 0) && (
              <Typography
                sx={{
                  position: 'absolute',
                  right: 2,
                  bottom: 2,
                  fontSize: `${squareSize * 0.15}px`,
                  color: squareColor === 'light' ? '#b58863' : '#f0d9b5',
                  fontWeight: 'bold',
                  pointerEvents: 'none',
                }}
              >
                {'abcdefgh'[orientation === 'white' ? file : 7 - file]}
              </Typography>
            )}
          </>
        )}
      </Box>
    );
  };

  // 渲染棋盘
  const renderBoard = () => {
    const squares = [];
    for (let rank = 0; rank < 8; rank++) {
      for (let file = 0; file < 8; file++) {
        squares.push(renderSquare(file, rank));
      }
    }
    return squares;
  };

  return (
    <Paper
      elevation={3}
      sx={{
        display: 'inline-block',
        p: 1,
        backgroundColor: '#8b4513',
      }}
    >
      <Box
        sx={{
          width: size,
          height: size,
          display: 'grid',
          gridTemplateColumns: 'repeat(8, 1fr)',
          gridTemplateRows: 'repeat(8, 1fr)',
          border: '1px solid #654321',
          borderRadius: 1,
          overflow: 'hidden',
        }}
      >
        {renderBoard()}
      </Box>
    </Paper>
  );
};

export default ChessBoard;
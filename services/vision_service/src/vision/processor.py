"""
视觉处理核心模块
处理RGB-D图像，检测棋盘和棋子
"""
import asyncio
import cv2
import numpy as np
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from shared.utils.logger import get_logger
from shared.models.chess_models import (
    ChessBoard, ChessPiece, PieceType, PieceColor,
    VisionDetection, ChessMove, Position3D
)
from .camera import RGBDFrame

logger = get_logger(__name__)


class DetectionMode(Enum):
    """检测模式"""
    BOARD_ONLY = "board_only"          # 仅检测棋盘
    PIECES_ONLY = "pieces_only"        # 仅检测棋子
    FULL_DETECTION = "full_detection"   # 完整检测
    MOVE_DETECTION = "move_detection"   # 移动检测


@dataclass
class BoardDetectionResult:
    """棋盘检测结果"""
    corners: np.ndarray  # 棋盘四个角点
    squares: Dict[str, Tuple[int, int, int, int]]  # 每个格子的边界框
    transform_matrix: np.ndarray  # 透视变换矩阵
    confidence: float
    board_area: float


@dataclass
class PieceDetectionResult:
    """棋子检测结果"""
    position: str  # 棋盘坐标 (如 "e4")
    piece_type: PieceType
    bounding_box: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    center_3d: Optional[Position3D] = None
    height: float = 0.0  # 棋子高度 (mm)


class VisionProcessor:
    """视觉处理器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # 棋盘检测参数
        self.board_size = (7, 7)  # 内部角点数量
        self.square_size = 40.0   # 棋盘格子大小 (mm)

        # 棋子检测参数
        self.piece_height_ranges = {
            PieceType.WHITE_PAWN: (15, 25),
            PieceType.WHITE_ROOK: (20, 30),
            PieceType.WHITE_KNIGHT: (25, 35),
            PieceType.WHITE_BISHOP: (25, 35),
            PieceType.WHITE_QUEEN: (30, 40),
            PieceType.WHITE_KING: (35, 45),
            PieceType.BLACK_PAWN: (15, 25),
            PieceType.BLACK_ROOK: (20, 30),
            PieceType.BLACK_KNIGHT: (25, 35),
            PieceType.BLACK_BISHOP: (25, 35),
            PieceType.BLACK_QUEEN: (30, 40),
            PieceType.BLACK_KING: (35, 45)
        }

        # 检测状态
        self.last_board_detection = None
        self.last_pieces = {}
        self.board_template = None

        # 性能统计
        self.processing_times = []

    async def process_frame(self,
                          frame: RGBDFrame,
                          mode: DetectionMode = DetectionMode.FULL_DETECTION) -> VisionDetection:
        """处理单帧图像"""
        start_time = time.time()

        try:
            logger.debug("开始处理视觉帧", frame_id=frame.frame_id, mode=mode.value)

            detected_move = None
            board_state = None
            detection_confidence = 0.0

            if mode in [DetectionMode.BOARD_ONLY, DetectionMode.FULL_DETECTION]:
                # 检测棋盘
                board_result = await self._detect_board(frame)
                if board_result:
                    detection_confidence = max(detection_confidence, board_result.confidence)
                    self.last_board_detection = board_result

            if mode in [DetectionMode.PIECES_ONLY, DetectionMode.FULL_DETECTION]:
                # 检测棋子
                if self.last_board_detection:
                    pieces = await self._detect_pieces(frame, self.last_board_detection)
                    board_state = self._create_board_state(pieces, frame.timestamp)
                    if pieces:
                        avg_confidence = sum(p.confidence for p in pieces) / len(pieces)
                        detection_confidence = max(detection_confidence, avg_confidence)

            if mode == DetectionMode.MOVE_DETECTION:
                # 检测移动
                detected_move = await self._detect_move(frame)
                if detected_move:
                    detection_confidence = 0.8  # 移动检测的固定置信度

            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)

            # 保持统计列表长度
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)

            logger.debug("视觉处理完成",
                        processing_time=processing_time,
                        confidence=detection_confidence)

            return VisionDetection(
                board_state=board_state,
                detected_move=detected_move,
                detection_confidence=detection_confidence,
                processing_time=processing_time,
                image_timestamp=frame.timestamp,
                camera_id=frame.camera_id
            )

        except Exception as e:
            logger.error("视觉处理异常", error=str(e), frame_id=frame.frame_id)
            return VisionDetection(
                board_state=None,
                detected_move=None,
                detection_confidence=0.0,
                processing_time=time.time() - start_time,
                image_timestamp=frame.timestamp,
                camera_id=frame.camera_id
            )

    async def _detect_board(self, frame: RGBDFrame) -> Optional[BoardDetectionResult]:
        """检测棋盘"""
        try:
            rgb_frame = frame.rgb_frame
            gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)

            # 使用棋盘格检测
            found, corners = cv2.findChessboardCorners(
                gray,
                self.board_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            )

            if found:
                # 细化角点
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

                # 计算棋盘区域
                corner_points = corners.reshape(-1, 2)
                board_corners = self._get_board_corners(corner_points)

                # 计算透视变换矩阵
                transform_matrix = self._calculate_transform_matrix(board_corners)

                # 生成格子坐标
                squares = self._generate_square_coordinates(board_corners)

                # 计算置信度
                confidence = self._calculate_board_confidence(gray, board_corners)

                return BoardDetectionResult(
                    corners=board_corners,
                    squares=squares,
                    transform_matrix=transform_matrix,
                    confidence=confidence,
                    board_area=cv2.contourArea(board_corners)
                )

            logger.debug("未检测到棋盘")
            return None

        except Exception as e:
            logger.error("棋盘检测异常", error=str(e))
            return None

    def _get_board_corners(self, corner_points: np.ndarray) -> np.ndarray:
        """从内部角点计算棋盘四个角点"""
        # 获取角点的边界
        min_x, min_y = corner_points.min(axis=0)
        max_x, max_y = corner_points.max(axis=0)

        # 估算棋盘外边界（扩展一个格子的大小）
        grid_size_x = (max_x - min_x) / (self.board_size[0] - 1)
        grid_size_y = (max_y - min_y) / (self.board_size[1] - 1)

        board_corners = np.array([
            [min_x - grid_size_x, min_y - grid_size_y],  # 左上
            [max_x + grid_size_x, min_y - grid_size_y],  # 右上
            [max_x + grid_size_x, max_y + grid_size_y],  # 右下
            [min_x - grid_size_x, max_y + grid_size_y]   # 左下
        ], dtype=np.float32)

        return board_corners

    def _calculate_transform_matrix(self, board_corners: np.ndarray) -> np.ndarray:
        """计算透视变换矩阵"""
        # 定义标准棋盘坐标（8x8）
        board_size_mm = self.square_size * 8
        dst_points = np.array([
            [0, 0],
            [board_size_mm, 0],
            [board_size_mm, board_size_mm],
            [0, board_size_mm]
        ], dtype=np.float32)

        return cv2.getPerspectiveTransform(board_corners, dst_points)

    def _generate_square_coordinates(self, board_corners: np.ndarray) -> Dict[str, Tuple[int, int, int, int]]:
        """生成每个格子的坐标"""
        squares = {}

        # 计算格子大小
        width = np.linalg.norm(board_corners[1] - board_corners[0]) / 8
        height = np.linalg.norm(board_corners[3] - board_corners[0]) / 8

        for row in range(8):
            for col in range(8):
                # 棋盘坐标
                square_name = chr(ord('a') + col) + str(row + 1)

                # 计算格子中心和边界
                center_x = board_corners[0][0] + (col + 0.5) * width
                center_y = board_corners[0][1] + (row + 0.5) * height

                # 边界框
                x = int(center_x - width / 2)
                y = int(center_y - height / 2)
                w = int(width)
                h = int(height)

                squares[square_name] = (x, y, w, h)

        return squares

    def _calculate_board_confidence(self, gray: np.ndarray, corners: np.ndarray) -> float:
        """计算棋盘检测置信度"""
        try:
            # 基于边缘检测的置信度
            edges = cv2.Canny(gray, 50, 150)

            # 在棋盘区域内计算边缘密度
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.fillPoly(mask, [corners.astype(np.int32)], 255)

            board_edges = cv2.bitwise_and(edges, mask)
            edge_density = np.sum(board_edges > 0) / np.sum(mask > 0)

            # 置信度映射到0-1范围
            confidence = min(edge_density * 5.0, 1.0)  # 调整系数

            return confidence

        except Exception as e:
            logger.error("置信度计算异常", error=str(e))
            return 0.5

    async def _detect_pieces(self,
                           frame: RGBDFrame,
                           board_result: BoardDetectionResult) -> List[PieceDetectionResult]:
        """检测棋子"""
        pieces = []

        try:
            rgb_frame = frame.rgb_frame
            depth_frame = frame.depth_frame

            for square_name, (x, y, w, h) in board_result.squares.items():
                # 提取格子区域
                roi_rgb = rgb_frame[y:y+h, x:x+w]
                roi_depth = depth_frame[y:y+h, x:x+w] if depth_frame is not None else None

                # 检测该格子是否有棋子
                piece_info = await self._detect_piece_in_square(
                    roi_rgb, roi_depth, square_name, (x, y, w, h)
                )

                if piece_info:
                    pieces.append(piece_info)

            logger.debug("检测到棋子", count=len(pieces))
            return pieces

        except Exception as e:
            logger.error("棋子检测异常", error=str(e))
            return pieces

    async def _detect_piece_in_square(self,
                                    roi_rgb: np.ndarray,
                                    roi_depth: Optional[np.ndarray],
                                    square_name: str,
                                    bbox: Tuple[int, int, int, int]) -> Optional[PieceDetectionResult]:
        """检测单个格子中的棋子"""
        try:
            # 简单的棋子检测算法
            gray = cv2.cvtColor(roi_rgb, cv2.COLOR_BGR2GRAY)

            # 阈值化处理
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # 查找轮廓
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return None

            # 找到最大轮廓
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)

            # 面积阈值判断是否有棋子
            min_area = (roi_rgb.shape[0] * roi_rgb.shape[1]) * 0.1  # 至少占10%
            if area < min_area:
                return None

            # 估算棋子类型（基于颜色和形状）
            piece_type = self._classify_piece(roi_rgb, roi_depth)

            # 计算3D中心点
            center_3d = None
            height = 0.0
            if roi_depth is not None:
                center_3d, height = self._calculate_3d_center(roi_depth, bbox)

            # 置信度（基于轮廓完整性和大小）
            perimeter = cv2.arcLength(largest_contour, True)
            compactness = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
            confidence = min(compactness * 2.0, 1.0)

            return PieceDetectionResult(
                position=square_name,
                piece_type=piece_type,
                bounding_box=bbox,
                confidence=confidence,
                center_3d=center_3d,
                height=height
            )

        except Exception as e:
            logger.error("格子棋子检测异常", error=str(e), square=square_name)
            return None

    def _classify_piece(self, roi_rgb: np.ndarray, roi_depth: Optional[np.ndarray]) -> PieceType:
        """分类棋子类型（简化版本）"""
        # 基于颜色判断黑白
        mean_color = np.mean(roi_rgb)
        is_white = mean_color > 128

        # 基于高度估算棋子类型（如果有深度信息）
        estimated_height = 25.0  # 默认高度
        if roi_depth is not None:
            depth_values = roi_depth[roi_depth > 0]
            if len(depth_values) > 0:
                estimated_height = np.median(depth_values)

        # 简单的高度到类型映射
        if estimated_height < 20:
            piece_type = PieceType.WHITE_PAWN if is_white else PieceType.BLACK_PAWN
        elif estimated_height < 30:
            piece_type = PieceType.WHITE_ROOK if is_white else PieceType.BLACK_ROOK
        elif estimated_height < 40:
            piece_type = PieceType.WHITE_KNIGHT if is_white else PieceType.BLACK_KNIGHT
        else:
            piece_type = PieceType.WHITE_KING if is_white else PieceType.BLACK_KING

        return piece_type

    def _calculate_3d_center(self, roi_depth: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[Optional[Position3D], float]:
        """计算3D中心点"""
        try:
            # 过滤有效深度值
            valid_depths = roi_depth[roi_depth > 0]
            if len(valid_depths) == 0:
                return None, 0.0

            # 计算中心深度
            center_depth = np.median(valid_depths)
            height = np.max(valid_depths) - np.min(valid_depths)

            # 计算2D中心
            x, y, w, h = bbox
            center_x = x + w // 2
            center_y = y + h // 2

            # 3D坐标（需要相机内参进行准确转换，这里使用简化计算）
            center_3d = Position3D(
                x=center_x,
                y=center_y,
                z=center_depth
            )

            return center_3d, height

        except Exception as e:
            logger.error("3D中心点计算异常", error=str(e))
            return None, 0.0

    def _create_board_state(self, pieces: List[PieceDetectionResult], timestamp: float) -> ChessBoard:
        """创建棋盘状态"""
        piece_dict = {}

        for piece_result in pieces:
            chess_piece = ChessPiece(
                piece_type=piece_result.piece_type,
                position=piece_result.position,
                color=self._get_piece_color(piece_result.piece_type),
                confidence=piece_result.confidence,
                physical_pos=piece_result.center_3d
            )
            piece_dict[piece_result.position] = chess_piece

        # 生成简化的FEN字符串（实际应用中需要更完整的逻辑）
        fen_string = self._generate_fen(piece_dict)

        return ChessBoard(
            pieces=piece_dict,
            timestamp=timestamp,
            fen_string=fen_string,
            move_count=0  # 需要从游戏状态获取
        )

    def _get_piece_color(self, piece_type: PieceType) -> PieceColor:
        """获取棋子颜色"""
        return PieceColor.WHITE if "white" in piece_type.value else PieceColor.BLACK

    def _generate_fen(self, pieces: Dict[str, ChessPiece]) -> str:
        """生成简化的FEN字符串"""
        # 这里返回一个占位FEN，实际应用中需要完整实现
        return "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    async def _detect_move(self, frame: RGBDFrame) -> Optional[ChessMove]:
        """检测棋子移动"""
        # 移动检测需要比较当前帧与历史帧
        # 这里返回None作为占位，实际实现需要帧间比较
        return None

    def get_performance_stats(self) -> Dict[str, float]:
        """获取性能统计"""
        if not self.processing_times:
            return {"avg_processing_time": 0.0, "fps": 0.0}

        avg_time = sum(self.processing_times) / len(self.processing_times)
        fps = 1.0 / avg_time if avg_time > 0 else 0.0

        return {
            "avg_processing_time": avg_time,
            "fps": fps,
            "min_processing_time": min(self.processing_times),
            "max_processing_time": max(self.processing_times)
        }
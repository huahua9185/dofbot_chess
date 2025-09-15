"""
Stockfish AI引擎控制器
"""
import asyncio
import subprocess
import time
import json
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import asdict
import chess
import chess.engine
import logging

from shared.models.chess_models import AIAnalysis, ChessBoard, ChessMove, GameState
from shared.utils.logger import get_logger
from shared.config.settings import get_settings

settings = get_settings()
logger = get_logger(__name__)


class StockfishEngine:
    """Stockfish象棋引擎控制器"""

    def __init__(self):
        self.stockfish_path = settings.ai.stockfish_path
        self.default_difficulty = settings.ai.default_difficulty
        self.max_thinking_time = settings.ai.max_thinking_time
        self.hash_size = settings.ai.hash_size
        self.threads = settings.ai.threads

        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.current_board = chess.Board()
        self.is_running = False
        self.difficulty_level = self.default_difficulty
        self.thinking_time = self.max_thinking_time

        # 难度级别配置 (1-10级)
        self.difficulty_configs = {
            1: {"depth": 1, "time": 0.1, "skill_level": 0},   # 最简单
            2: {"depth": 2, "time": 0.5, "skill_level": 2},
            3: {"depth": 3, "time": 1.0, "skill_level": 5},   # 默认
            4: {"depth": 4, "time": 2.0, "skill_level": 8},
            5: {"depth": 5, "time": 3.0, "skill_level": 10},
            6: {"depth": 6, "time": 5.0, "skill_level": 12},
            7: {"depth": 8, "time": 8.0, "skill_level": 15},
            8: {"depth": 10, "time": 12.0, "skill_level": 17},
            9: {"depth": 12, "time": 15.0, "skill_level": 19},
            10: {"depth": 15, "time": 20.0, "skill_level": 20} # 最困难
        }

    async def initialize(self) -> bool:
        """初始化Stockfish引擎"""
        try:
            logger.info(f"初始化Stockfish引擎: {self.stockfish_path}")

            # 启动引擎
            transport, engine = await chess.engine.popen_uci(self.stockfish_path)
            self.engine = engine

            # 配置引擎参数
            await self._configure_engine()

            self.is_running = True
            logger.info("Stockfish引擎初始化成功")
            return True

        except Exception as e:
            logger.error(f"初始化Stockfish失败: {str(e)}")
            return False

    async def _configure_engine(self):
        """配置引擎参数"""
        if not self.engine:
            return

        try:
            # 设置哈希表大小
            await self.engine.configure({"Hash": self.hash_size})

            # 设置线程数
            await self.engine.configure({"Threads": self.threads})

            # 设置技能等级
            config = self.difficulty_configs[self.difficulty_level]
            await self.engine.configure({"Skill Level": config["skill_level"]})

            logger.info(f"引擎配置完成 - 难度:{self.difficulty_level}, 哈希:{self.hash_size}MB, 线程:{self.threads}")

        except Exception as e:
            logger.error(f"配置引擎参数失败: {str(e)}")

    async def shutdown(self):
        """关闭引擎"""
        if self.engine:
            try:
                await self.engine.quit()
                logger.info("Stockfish引擎已关闭")
            except Exception as e:
                logger.error(f"关闭引擎失败: {str(e)}")
        self.is_running = False

    def set_difficulty(self, level: int):
        """设置难度级别 (1-10)"""
        if 1 <= level <= 10:
            self.difficulty_level = level
            logger.info(f"设置AI难度为: {level}级")
        else:
            logger.warning(f"无效的难度级别: {level}")

    def set_position_from_fen(self, fen: str):
        """从FEN字符串设置棋盘位置"""
        try:
            self.current_board = chess.Board(fen)
            logger.info(f"棋盘位置已更新: {fen}")
        except Exception as e:
            logger.error(f"设置FEN位置失败: {str(e)}")

    def set_position_from_moves(self, moves: List[str]):
        """从移动序列设置棋盘位置"""
        try:
            self.current_board = chess.Board()
            for move_str in moves:
                move = chess.Move.from_uci(move_str)
                self.current_board.push(move)
            logger.info(f"棋盘位置已更新，移动数: {len(moves)}")
        except Exception as e:
            logger.error(f"设置移动序列失败: {str(e)}")

    async def get_best_move(self, time_limit: Optional[float] = None) -> Optional[AIAnalysis]:
        """获取最佳移动"""
        if not self.engine or not self.is_running:
            logger.error("引擎未初始化或未运行")
            return None

        try:
            start_time = time.time()
            config = self.difficulty_configs[self.difficulty_level]

            # 使用时间限制或深度限制
            if time_limit:
                limit = chess.engine.Limit(time=time_limit)
            else:
                limit = chess.engine.Limit(
                    time=config["time"],
                    depth=config["depth"]
                )

            logger.info(f"AI思考中... 难度:{self.difficulty_level}, 限制:{limit}")

            # 分析当前位置
            result = await self.engine.play(self.current_board, limit)
            thinking_time = time.time() - start_time

            if result.move is None:
                logger.warning("引擎未找到有效移动")
                return None

            # 获取详细分析信息
            info = await self._get_position_analysis(limit)

            analysis = AIAnalysis(
                best_move=result.move.uci(),
                evaluation=info.get("evaluation", 0.0),
                depth=info.get("depth", 0),
                nodes=info.get("nodes", 0),
                thinking_time=thinking_time,
                principal_variation=info.get("pv", []),
                confidence=min(1.0, max(0.1, 1.0 - abs(info.get("evaluation", 0)) / 1000))
            )

            logger.info(f"AI分析完成: {result.move.uci()}, 评估:{analysis.evaluation:.2f}, 时间:{thinking_time:.2f}s")
            return analysis

        except Exception as e:
            logger.error(f"获取最佳移动失败: {str(e)}")
            return None

    async def _get_position_analysis(self, limit: chess.engine.Limit) -> Dict[str, Any]:
        """获取位置分析信息"""
        try:
            analysis = await self.engine.analyse(self.current_board, limit)

            # 提取分析信息
            info = {}

            if "score" in analysis:
                score = analysis["score"]
                if score.is_mate():
                    # 将死分数
                    mate_in = score.mate()
                    info["evaluation"] = 9999 if mate_in > 0 else -9999
                else:
                    # 厘兵分数转换为常规分数
                    info["evaluation"] = score.score() / 100.0 if score.score() else 0.0

            info["depth"] = analysis.get("depth", 0)
            info["nodes"] = analysis.get("nodes", 0)

            # 主变着法
            if "pv" in analysis:
                info["pv"] = [move.uci() for move in analysis["pv"]]

            return info

        except Exception as e:
            logger.error(f"获取分析信息失败: {str(e)}")
            return {}

    async def evaluate_position(self) -> float:
        """评估当前位置"""
        if not self.engine or not self.is_running:
            return 0.0

        try:
            limit = chess.engine.Limit(time=1.0)  # 快速评估
            analysis = await self.engine.analyse(self.current_board, limit)

            if "score" in analysis:
                score = analysis["score"]
                if score.is_mate():
                    mate_in = score.mate()
                    return 9999 if mate_in > 0 else -9999
                else:
                    return score.score() / 100.0 if score.score() else 0.0

            return 0.0

        except Exception as e:
            logger.error(f"评估位置失败: {str(e)}")
            return 0.0

    async def is_game_over(self) -> Tuple[bool, Optional[str]]:
        """检查游戏是否结束"""
        try:
            if self.current_board.is_checkmate():
                winner = "white" if self.current_board.turn == chess.BLACK else "black"
                return True, f"checkmate_{winner}"

            if self.current_board.is_stalemate():
                return True, "stalemate"

            if self.current_board.is_insufficient_material():
                return True, "insufficient_material"

            if self.current_board.is_seventyfive_moves():
                return True, "seventyfive_moves"

            if self.current_board.is_fivefold_repetition():
                return True, "fivefold_repetition"

            return False, None

        except Exception as e:
            logger.error(f"检查游戏结束状态失败: {str(e)}")
            return False, None

    def make_move(self, move_uci: str) -> bool:
        """在棋盘上执行移动"""
        try:
            move = chess.Move.from_uci(move_uci)
            if move in self.current_board.legal_moves:
                self.current_board.push(move)
                logger.info(f"移动执行: {move_uci}")
                return True
            else:
                logger.warning(f"非法移动: {move_uci}")
                return False

        except Exception as e:
            logger.error(f"执行移动失败: {str(e)}")
            return False

    def undo_move(self) -> bool:
        """撤销上一步移动"""
        try:
            if len(self.current_board.move_stack) > 0:
                self.current_board.pop()
                logger.info("撤销移动成功")
                return True
            else:
                logger.warning("没有可撤销的移动")
                return False

        except Exception as e:
            logger.error(f"撤销移动失败: {str(e)}")
            return False

    def get_legal_moves(self) -> List[str]:
        """获取所有合法移动"""
        try:
            return [move.uci() for move in self.current_board.legal_moves]
        except Exception as e:
            logger.error(f"获取合法移动失败: {str(e)}")
            return []

    def is_move_legal(self, move_uci: str) -> bool:
        """检查移动是否合法"""
        try:
            move = chess.Move.from_uci(move_uci)
            return move in self.current_board.legal_moves
        except Exception as e:
            logger.error(f"检查移动合法性失败: {str(e)}")
            return False

    def get_board_fen(self) -> str:
        """获取棋盘FEN字符串"""
        return self.current_board.fen()

    def get_move_history(self) -> List[str]:
        """获取移动历史"""
        return [move.uci() for move in self.current_board.move_stack]

    async def suggest_moves(self, count: int = 3) -> List[Dict[str, Any]]:
        """建议多个移动选项"""
        if not self.engine or not self.is_running:
            return []

        try:
            suggestions = []
            limit = chess.engine.Limit(time=2.0, depth=8)

            # 获取多个候选移动
            analysis = await self.engine.analyse(
                self.current_board,
                limit,
                multipv=min(count, len(list(self.current_board.legal_moves)))
            )

            for i, pv_info in enumerate(analysis):
                if "pv" in pv_info and len(pv_info["pv"]) > 0:
                    move = pv_info["pv"][0]
                    score = pv_info.get("score", None)

                    eval_score = 0.0
                    if score:
                        if score.is_mate():
                            eval_score = 9999 if score.mate() > 0 else -9999
                        else:
                            eval_score = score.score() / 100.0 if score.score() else 0.0

                    suggestions.append({
                        "move": move.uci(),
                        "evaluation": eval_score,
                        "rank": i + 1,
                        "depth": pv_info.get("depth", 0),
                        "pv": [m.uci() for m in pv_info["pv"][:5]]  # 显示前5步
                    })

            return suggestions

        except Exception as e:
            logger.error(f"获取移动建议失败: {str(e)}")
            return []

    async def analyze_game(self, moves: List[str]) -> Dict[str, Any]:
        """分析整局游戏"""
        try:
            analysis_result = {
                "total_moves": len(moves),
                "game_result": "unknown",
                "move_analysis": [],
                "accuracy": {"white": 0.0, "black": 0.0},
                "blunders": [],
                "best_moves": []
            }

            # 重置棋盘
            temp_board = chess.Board()

            for i, move_uci in enumerate(moves):
                move = chess.Move.from_uci(move_uci)
                current_player = "white" if temp_board.turn == chess.WHITE else "black"

                # 分析移动前的最佳选择
                if self.engine:
                    limit = chess.engine.Limit(time=1.0, depth=8)
                    best_move_result = await self.engine.play(temp_board, limit)

                    move_eval = {
                        "move_number": i + 1,
                        "player": current_player,
                        "move": move_uci,
                        "best_move": best_move_result.move.uci() if best_move_result.move else None,
                        "is_best": move == best_move_result.move if best_move_result.move else False
                    }

                    analysis_result["move_analysis"].append(move_eval)

                    if move_eval["is_best"]:
                        analysis_result["best_moves"].append(move_eval)

                temp_board.push(move)

            # 计算准确度
            white_moves = [m for m in analysis_result["move_analysis"] if m["player"] == "white"]
            black_moves = [m for m in analysis_result["move_analysis"] if m["player"] == "black"]

            if white_moves:
                analysis_result["accuracy"]["white"] = sum(1 for m in white_moves if m["is_best"]) / len(white_moves)
            if black_moves:
                analysis_result["accuracy"]["black"] = sum(1 for m in black_moves if m["is_best"]) / len(black_moves)

            return analysis_result

        except Exception as e:
            logger.error(f"分析游戏失败: {str(e)}")
            return {"error": str(e)}

    def get_engine_info(self) -> Dict[str, Any]:
        """获取引擎信息"""
        return {
            "engine_path": self.stockfish_path,
            "is_running": self.is_running,
            "difficulty_level": self.difficulty_level,
            "hash_size": self.hash_size,
            "threads": self.threads,
            "current_fen": self.get_board_fen(),
            "move_count": len(self.current_board.move_stack),
            "legal_moves_count": len(list(self.current_board.legal_moves))
        }
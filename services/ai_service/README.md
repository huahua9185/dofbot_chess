# AI Engine Service

基于Stockfish的象棋AI引擎服务，提供可调节难度的AI对弈功能。

## 功能特性

- **Stockfish引擎**: 集成世界顶级开源象棋引擎
- **多难度级别**: 1-10级可调节难度，适合不同水平玩家
- **实时分析**: 位置评估、最佳移动建议、主变着法分析
- **游戏分析**: 整局复盘、移动准确度统计、失误检测
- **事件驱动**: 基于Redis的异步消息处理
- **高性能**: 多线程搜索、哈希表优化

## 技术实现

### Stockfish引擎集成
- **UCI协议**: 标准国际象棋引擎通信协议
- **异步操作**: 非阻塞的引擎通信和分析
- **资源管理**: 合理配置内存和计算资源
- **错误处理**: 完整的引擎异常处理机制

### 难度系统
智能难度调节系统，通过多维度参数控制AI强度：

| 难度 | 搜索深度 | 思考时间 | 技能等级 | 适用对象 |
|------|----------|----------|----------|----------|
| 1级  | 1层      | 0.1秒    | 0        | 初学者   |
| 3级  | 3层      | 1.0秒    | 5        | 业余爱好者 |
| 5级  | 5层      | 3.0秒    | 10       | 中级玩家 |
| 8级  | 10层     | 12.0秒   | 17       | 高级玩家 |
| 10级 | 15层     | 20.0秒   | 20       | 专业水平 |

### 分析功能
1. **位置评估**: 实时评估当前局面优劣
2. **移动建议**: 提供多个候选移动及评分
3. **主变着法**: 显示引擎计算的最佳变化
4. **游戏复盘**: 分析整局游戏的移动质量

## API接口

### 引擎控制
```python
# 设置难度
engine.set_difficulty(5)

# 设置棋盘位置
engine.set_position_from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

# 获取最佳移动
analysis = await engine.get_best_move(time_limit=5.0)
# 返回: AIAnalysis对象，包含移动、评估、搜索信息等
```

### 游戏分析
```python
# 位置评估
evaluation = await engine.evaluate_position()

# 移动建议
suggestions = await engine.suggest_moves(count=3)

# 整局分析
game_analysis = await engine.analyze_game(moves_list)
```

### 事件系统
服务通过Redis事件总线处理以下消息：

**输入事件**:
- `game_started`: 游戏开始，初始化AI状态
- `move_made`: 玩家移动，更新棋盘状态
- `ai_move_request`: 请求AI移动
- `difficulty_changed`: 调整AI难度
- `analysis_request`: 请求分析功能

**输出事件**:
- `ai_move_result`: AI移动结果和分析
- `ai_analysis_result`: 分析结果
- `ai_status_update`: AI引擎状态
- `game_over`: 游戏结束通知

## 配置参数

在 `shared/config/settings.py` 中配置：

```python
class AISettings:
    stockfish_path: str = "stockfish"         # Stockfish可执行文件路径
    default_difficulty: int = 3               # 默认难度级别
    max_thinking_time: float = 10.0           # 最大思考时间
    hash_size: int = 128                      # 哈希表大小(MB)
    threads: int = 2                          # 搜索线程数
```

## 运行方式

### 直接运行
```bash
# 安装Stockfish
sudo apt-get install stockfish

# 安装Python依赖
cd services/ai_service
pip3 install -r requirements.txt

# 启动服务
python3 -m src.ai.service
```

### Docker运行
```bash
docker build -t ai-service .
docker run ai-service
```

### 开发调试
```bash
# 运行测试
pytest tests/ -v

# 交互式测试
python3 -c "
from src.ai.engine import StockfishEngine
import asyncio

async def test():
    engine = StockfishEngine()
    await engine.initialize()

    # 测试分析
    analysis = await engine.get_best_move()
    print(f'最佳移动: {analysis.best_move}')
    print(f'评估: {analysis.evaluation}')

    await engine.shutdown()

asyncio.run(test())
"
```

## 性能指标

- **响应时间**:
  - 简单难度: <0.5秒
  - 中等难度: 1-5秒
  - 高级难度: 5-20秒
- **分析精度**: 与Stockfish原生一致
- **内存使用**: 哈希表 + 30-50MB基础内存
- **CPU占用**: 可配置1-8线程，支持并行搜索

## 错误处理

### 常见问题
1. **Stockfish未安装**: 自动下载或提示安装路径
2. **内存不足**: 自动调整哈希表大小
3. **引擎崩溃**: 自动重启和状态恢复
4. **分析超时**: 返回当前最佳结果

### 调试方法
```bash
# 检查Stockfish安装
which stockfish
stockfish --help

# 测试引擎通信
echo "uci" | stockfish
echo "isready" | stockfish
```

## 扩展功能

### 自定义引擎参数
```python
# 高级配置示例
await engine.engine.configure({
    "Hash": 256,           # 更大哈希表
    "Threads": 4,          # 更多线程
    "Contempt": 10,        # 和棋倾向
    "Analysis Contempt": "Off"
})
```

### 开局库集成
```python
# 可扩展开局库功能
from chess.polyglot import open_reader

def get_opening_move(board):
    with open_reader("book.bin") as reader:
        entries = list(reader.find_all(board))
        if entries:
            return entries[0].move
    return None
```

### 残局库支持
```python
# 集成Syzygy残局库
import chess.syzygy

# 配置残局库路径
engine.configure({"SyzygyPath": "/path/to/tablebase"})
```

## 维护说明

### 性能优化
- 根据硬件调整线程数和哈希表大小
- 定期更新Stockfish版本获得性能提升
- 监控内存使用避免系统资源不足

### 日志分析
```bash
# 查看AI分析日志
tail -f logs/ai_service.log | grep "AI分析"

# 监控性能指标
grep "thinking_time" logs/ai_service.log | awk '{print $NF}'
```

### 升级维护
1. **引擎升级**: 定期更新Stockfish获得最新棋力
2. **参数调优**: 根据实际使用情况调整难度参数
3. **性能监控**: 关注响应时间和资源使用情况
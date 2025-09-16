#!/usr/bin/env python3
"""
日志分析工具
提供日志查询、分析和可视化功能
"""

import os
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
import re

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.logging.metrics import LogMetricsCollector


class LogAnalyzer:
    """日志分析器"""

    def __init__(self, log_dir: str = "/home/jetson/prog/logs"):
        self.log_dir = Path(log_dir)
        self.metrics = LogMetricsCollector()

    def parse_json_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析JSON格式的日志行"""
        try:
            return json.loads(line.strip())
        except (json.JSONDecodeError, ValueError):
            return None

    def read_log_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """读取并解析日志文件"""
        logs = []

        if not file_path.exists():
            print(f"日志文件不存在: {file_path}")
            return logs

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    log_entry = self.parse_json_log_line(line)
                    if log_entry:
                        log_entry['line_number'] = line_num
                        log_entry['file_path'] = str(file_path)
                        logs.append(log_entry)

        except Exception as e:
            print(f"读取日志文件失败 {file_path}: {e}")

        return logs

    def get_all_logs(self, services: List[str] = None) -> List[Dict[str, Any]]:
        """获取所有服务的日志"""
        all_logs = []

        # 默认服务列表
        if services is None:
            services = [
                'web_gateway', 'vision_service', 'robot_service',
                'ai_service', 'game_manager', 'calibration_service'
            ]

        for service in services:
            log_file = self.log_dir / f"{service}.log"
            service_logs = self.read_log_file(log_file)

            # 添加服务标识
            for log in service_logs:
                log['source_service'] = service

            all_logs.extend(service_logs)

        # 按时间戳排序
        all_logs.sort(key=lambda x: x.get('timestamp', ''))

        return all_logs

    def filter_logs(
        self,
        logs: List[Dict[str, Any]],
        level: str = None,
        service: str = None,
        event: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        search_text: str = None
    ) -> List[Dict[str, Any]]:
        """过滤日志"""
        filtered_logs = logs

        # 按级别过滤
        if level:
            filtered_logs = [log for log in filtered_logs if log.get('level', '').lower() == level.lower()]

        # 按服务过滤
        if service:
            filtered_logs = [log for log in filtered_logs if log.get('service') == service or log.get('source_service') == service]

        # 按事件类型过滤
        if event:
            filtered_logs = [log for log in filtered_logs if log.get('event') == event]

        # 按时间范围过滤
        if start_time or end_time:
            time_filtered = []
            for log in filtered_logs:
                log_time_str = log.get('timestamp', '')
                if log_time_str:
                    try:
                        log_time = datetime.fromisoformat(log_time_str.replace('Z', '+00:00'))
                        if start_time and log_time < start_time:
                            continue
                        if end_time and log_time > end_time:
                            continue
                        time_filtered.append(log)
                    except ValueError:
                        continue
            filtered_logs = time_filtered

        # 按文本搜索过滤
        if search_text:
            pattern = re.compile(search_text, re.IGNORECASE)
            text_filtered = []
            for log in filtered_logs:
                # 搜索消息内容
                if pattern.search(log.get('message', '')):
                    text_filtered.append(log)
                    continue
                # 搜索错误信息
                if pattern.search(log.get('error_message', '')):
                    text_filtered.append(log)
                    continue
                # 搜索其他字段
                log_str = json.dumps(log, default=str)
                if pattern.search(log_str):
                    text_filtered.append(log)
            filtered_logs = text_filtered

        return filtered_logs

    def analyze_error_patterns(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析错误模式"""
        error_logs = [log for log in logs if log.get('level', '').lower() == 'error']

        if not error_logs:
            return {'total_errors': 0, 'patterns': {}}

        # 统计错误类型
        error_types = Counter(log.get('error_type', 'Unknown') for log in error_logs)

        # 统计错误消息模式
        error_messages = Counter(log.get('error_message', 'Unknown') for log in error_logs)

        # 按服务统计错误
        errors_by_service = defaultdict(int)
        for log in error_logs:
            service = log.get('service', log.get('source_service', 'Unknown'))
            errors_by_service[service] += 1

        # 按时间统计错误（按小时）
        errors_by_hour = defaultdict(int)
        for log in error_logs:
            timestamp = log.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hour_key = dt.strftime('%Y-%m-%d %H:00')
                    errors_by_hour[hour_key] += 1
                except ValueError:
                    continue

        return {
            'total_errors': len(error_logs),
            'error_types': dict(error_types.most_common(10)),
            'error_messages': dict(error_messages.most_common(10)),
            'errors_by_service': dict(errors_by_service),
            'errors_by_hour': dict(sorted(errors_by_hour.items()))
        }

    def analyze_performance_metrics(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析性能指标"""
        performance_logs = [log for log in logs if 'duration_seconds' in log]

        if not performance_logs:
            return {'total_operations': 0, 'metrics': {}}

        # 按功能统计执行时间
        duration_by_function = defaultdict(list)
        for log in performance_logs:
            func_name = log.get('function', log.get('function_name', 'Unknown'))
            duration = log.get('duration_seconds', 0)
            duration_by_function[func_name].append(duration)

        # 计算统计信息
        function_stats = {}
        for func_name, durations in duration_by_function.items():
            if durations:
                function_stats[func_name] = {
                    'count': len(durations),
                    'avg_duration': sum(durations) / len(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'total_duration': sum(durations)
                }

        return {
            'total_operations': len(performance_logs),
            'function_stats': function_stats
        }

    def generate_report(self, logs: List[Dict[str, Any]]) -> str:
        """生成分析报告"""
        if not logs:
            return "没有找到日志数据"

        total_logs = len(logs)

        # 统计日志级别
        level_counts = Counter(log.get('level', 'Unknown') for log in logs)

        # 统计服务
        service_counts = Counter(log.get('service', log.get('source_service', 'Unknown')) for log in logs)

        # 统计事件类型
        event_counts = Counter(log.get('event', 'Unknown') for log in logs if log.get('event'))

        # 时间范围
        timestamps = [log.get('timestamp') for log in logs if log.get('timestamp')]
        timestamps = [ts for ts in timestamps if ts]
        time_range = ""
        if timestamps:
            try:
                start_time = min(timestamps)
                end_time = max(timestamps)
                time_range = f"从 {start_time} 到 {end_time}"
            except ValueError:
                time_range = "时间格式解析失败"

        # 分析错误和性能
        error_analysis = self.analyze_error_patterns(logs)
        performance_analysis = self.analyze_performance_metrics(logs)

        # 生成报告
        report = f"""
========================================
日志分析报告
========================================

基本统计:
- 总日志数: {total_logs}
- 时间范围: {time_range}

日志级别分布:
"""

        for level, count in level_counts.most_common():
            percentage = (count / total_logs) * 100
            report += f"- {level}: {count} ({percentage:.1f}%)\n"

        report += f"\n服务分布:\n"
        for service, count in service_counts.most_common():
            percentage = (count / total_logs) * 100
            report += f"- {service}: {count} ({percentage:.1f}%)\n"

        if event_counts:
            report += f"\n主要事件类型:\n"
            for event, count in event_counts.most_common(10):
                report += f"- {event}: {count}\n"

        if error_analysis['total_errors'] > 0:
            report += f"\n错误分析:\n"
            report += f"- 总错误数: {error_analysis['total_errors']}\n"

            if error_analysis['error_types']:
                report += "- 错误类型:\n"
                for error_type, count in error_analysis['error_types'].items():
                    report += f"  * {error_type}: {count}\n"

            if error_analysis['errors_by_service']:
                report += "- 按服务统计错误:\n"
                for service, count in error_analysis['errors_by_service'].items():
                    report += f"  * {service}: {count}\n"

        if performance_analysis['total_operations'] > 0:
            report += f"\n性能分析:\n"
            report += f"- 总操作数: {performance_analysis['total_operations']}\n"

            if performance_analysis['function_stats']:
                report += "- 性能最差的函数 (按平均执行时间):\n"
                sorted_functions = sorted(
                    performance_analysis['function_stats'].items(),
                    key=lambda x: x[1]['avg_duration'],
                    reverse=True
                )
                for func_name, stats in sorted_functions[:10]:
                    report += f"  * {func_name}: 平均 {stats['avg_duration']:.3f}s (调用 {stats['count']} 次)\n"

        report += "\n========================================"

        return report


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能象棋机器人日志分析工具")

    parser.add_argument("--log-dir", default="/home/jetson/prog/logs", help="日志文件目录")
    parser.add_argument("--service", help="指定服务名称")
    parser.add_argument("--level", help="日志级别过滤 (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--event", help="事件类型过滤")
    parser.add_argument("--search", help="搜索文本")
    parser.add_argument("--hours", type=int, help="显示最近N小时的日志")
    parser.add_argument("--report", action="store_true", help="生成分析报告")
    parser.add_argument("--output", help="输出文件路径")

    args = parser.parse_args()

    # 创建分析器
    analyzer = LogAnalyzer(args.log_dir)

    print(f"正在分析日志文件: {args.log_dir}")

    # 读取日志
    logs = analyzer.get_all_logs()
    print(f"读取到 {len(logs)} 条日志记录")

    # 时间过滤
    if args.hours:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=args.hours)
        logs = analyzer.filter_logs(logs, start_time=start_time, end_time=end_time)
        print(f"时间过滤后: {len(logs)} 条记录")

    # 应用其他过滤器
    logs = analyzer.filter_logs(
        logs,
        level=args.level,
        service=args.service,
        event=args.event,
        search_text=args.search
    )

    print(f"过滤后: {len(logs)} 条记录")

    if args.report:
        # 生成报告
        report = analyzer.generate_report(logs)

        if args.output:
            # 保存到文件
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"报告已保存到: {args.output}")
        else:
            # 打印到控制台
            print(report)
    else:
        # 显示日志
        for log in logs[-50:]:  # 显示最后50条
            timestamp = log.get('timestamp', 'Unknown')
            level = log.get('level', 'Unknown')
            service = log.get('service', log.get('source_service', 'Unknown'))
            message = log.get('message', 'No message')

            print(f"[{timestamp}] {level} {service}: {message}")

            # 如果有错误信息，显示错误详情
            if log.get('error_message'):
                print(f"  错误: {log['error_message']}")

            # 如果有执行时间，显示性能信息
            if log.get('duration_seconds'):
                print(f"  耗时: {log['duration_seconds']:.3f}s")


if __name__ == "__main__":
    main()
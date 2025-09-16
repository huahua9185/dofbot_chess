#!/usr/bin/env python3
"""
基于Web的日志分析服务
提供REST API接口查询和分析日志数据
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from elasticsearch import Elasticsearch

# 添加项目根目录到路径
sys.path.insert(0, '/app')

try:
    from tools.log_analyzer import LogAnalyzer
except ImportError:
    # 如果导入失败，创建一个简化版本
    class LogAnalyzer:
        def __init__(self, log_dir: str = "/app/logs"):
            self.log_dir = Path(log_dir)

        def get_all_logs(self, services: List[str] = None):
            return []

        def generate_report(self, logs: List[Dict]) -> str:
            return "日志分析器未正确初始化"


# 创建Flask应用
app = Flask(__name__)
CORS(app)

# 全局变量
es_client = None
log_analyzer = LogAnalyzer("/app/logs")


def get_elasticsearch_client():
    """获取Elasticsearch客户端"""
    global es_client
    if es_client is None:
        es_host = os.getenv('ELASTICSEARCH_HOST', 'localhost')
        es_port = int(os.getenv('ELASTICSEARCH_PORT', '9200'))

        try:
            es_client = Elasticsearch([{
                'host': es_host,
                'port': es_port,
                'scheme': 'http'
            }])

            # 测试连接
            if not es_client.ping():
                es_client = None
                print(f"无法连接到Elasticsearch: {es_host}:{es_port}")

        except Exception as e:
            print(f"Elasticsearch连接失败: {e}")
            es_client = None

    return es_client


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    es = get_elasticsearch_client()

    return jsonify({
        'status': 'healthy',
        'service': 'log_analyzer',
        'elasticsearch_available': es is not None,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/api/logs/search', methods=['GET'])
def search_logs():
    """搜索日志"""
    try:
        # 获取查询参数
        query = request.args.get('q', '*')
        service = request.args.get('service')
        level = request.args.get('level')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        size = int(request.args.get('size', 100))
        from_param = int(request.args.get('from', 0))

        es = get_elasticsearch_client()
        if es is None:
            # 回退到文件日志分析
            logs = log_analyzer.get_all_logs()

            # 简单过滤
            if service:
                logs = [log for log in logs if log.get('service') == service]
            if level:
                logs = [log for log in logs if log.get('level', '').lower() == level.lower()]

            return jsonify({
                'hits': {
                    'total': {'value': len(logs)},
                    'hits': [{'_source': log} for log in logs[from_param:from_param + size]]
                }
            })

        # 构建Elasticsearch查询
        es_query = {
            'query': {
                'bool': {
                    'must': []
                }
            },
            'sort': [
                {'@timestamp': {'order': 'desc'}}
            ],
            'size': size,
            'from': from_param
        }

        # 添加文本查询
        if query and query != '*':
            es_query['query']['bool']['must'].append({
                'multi_match': {
                    'query': query,
                    'fields': ['message', 'error_message', 'event', 'function']
                }
            })

        # 添加过滤条件
        if service:
            es_query['query']['bool']['must'].append({
                'term': {'service.keyword': service}
            })

        if level:
            es_query['query']['bool']['must'].append({
                'term': {'level.keyword': level.upper()}
            })

        # 时间范围过滤
        if start_time or end_time:
            time_range = {}
            if start_time:
                time_range['gte'] = start_time
            if end_time:
                time_range['lte'] = end_time

            es_query['query']['bool']['must'].append({
                'range': {'@timestamp': time_range}
            })

        # 执行搜索
        result = es.search(
            index='chess-logs-*',
            body=es_query
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': '搜索日志失败'
        }), 500


@app.route('/api/logs/stats', methods=['GET'])
def get_log_stats():
    """获取日志统计信息"""
    try:
        es = get_elasticsearch_client()
        if es is None:
            # 回退到文件日志分析
            logs = log_analyzer.get_all_logs()

            stats = {
                'total_logs': len(logs),
                'levels': {},
                'services': {},
                'recent_errors': []
            }

            for log in logs:
                level = log.get('level', 'Unknown')
                service = log.get('service', 'Unknown')

                stats['levels'][level] = stats['levels'].get(level, 0) + 1
                stats['services'][service] = stats['services'].get(service, 0) + 1

                if level.lower() == 'error':
                    stats['recent_errors'].append({
                        'timestamp': log.get('timestamp'),
                        'message': log.get('message'),
                        'service': service
                    })

            return jsonify(stats)

        # Elasticsearch聚合查询
        agg_query = {
            'query': {
                'range': {
                    '@timestamp': {
                        'gte': 'now-1d'
                    }
                }
            },
            'aggs': {
                'levels': {
                    'terms': {'field': 'level.keyword'}
                },
                'services': {
                    'terms': {'field': 'service.keyword'}
                },
                'errors_by_hour': {
                    'filter': {'term': {'level.keyword': 'ERROR'}},
                    'aggs': {
                        'by_hour': {
                            'date_histogram': {
                                'field': '@timestamp',
                                'calendar_interval': '1h'
                            }
                        }
                    }
                }
            },
            'size': 0
        }

        result = es.search(
            index='chess-logs-*',
            body=agg_query
        )

        # 获取最近的错误
        error_query = {
            'query': {
                'bool': {
                    'must': [
                        {'term': {'level.keyword': 'ERROR'}},
                        {'range': {'@timestamp': {'gte': 'now-1h'}}}
                    ]
                }
            },
            'sort': [{'@timestamp': {'order': 'desc'}}],
            'size': 10
        }

        error_result = es.search(
            index='chess-logs-*',
            body=error_query
        )

        stats = {
            'total_logs': result['hits']['total']['value'],
            'levels': {bucket['key']: bucket['doc_count'] for bucket in result['aggregations']['levels']['buckets']},
            'services': {bucket['key']: bucket['doc_count'] for bucket in result['aggregations']['services']['buckets']},
            'errors_by_hour': [
                {
                    'timestamp': bucket['key_as_string'],
                    'count': bucket['doc_count']
                } for bucket in result['aggregations']['errors_by_hour']['by_hour']['buckets']
            ],
            'recent_errors': [
                {
                    'timestamp': hit['_source'].get('@timestamp'),
                    'message': hit['_source'].get('message'),
                    'service': hit['_source'].get('service'),
                    'error_type': hit['_source'].get('error_type')
                } for hit in error_result['hits']['hits']
            ]
        }

        return jsonify(stats)

    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': '获取统计信息失败'
        }), 500


@app.route('/api/logs/analysis', methods=['GET'])
def get_log_analysis():
    """获取日志分析报告"""
    try:
        service = request.args.get('service')
        hours = int(request.args.get('hours', 24))

        es = get_elasticsearch_client()
        if es is None:
            # 回退到文件日志分析
            logs = log_analyzer.get_all_logs()
            report = log_analyzer.generate_report(logs)

            return jsonify({
                'report': report,
                'type': 'text'
            })

        # 时间范围
        start_time = datetime.utcnow() - timedelta(hours=hours)

        # 构建查询
        query = {
            'query': {
                'range': {
                    '@timestamp': {
                        'gte': start_time.isoformat()
                    }
                }
            },
            'aggs': {
                'error_analysis': {
                    'filter': {'term': {'level.keyword': 'ERROR'}},
                    'aggs': {
                        'error_types': {
                            'terms': {'field': 'error_type.keyword', 'size': 10}
                        },
                        'error_services': {
                            'terms': {'field': 'service.keyword', 'size': 10}
                        }
                    }
                },
                'performance_analysis': {
                    'filter': {'exists': {'field': 'duration_seconds'}},
                    'aggs': {
                        'avg_duration': {
                            'avg': {'field': 'duration_seconds'}
                        },
                        'slow_functions': {
                            'terms': {
                                'field': 'function.keyword',
                                'order': {'avg_duration': 'desc'},
                                'size': 10
                            },
                            'aggs': {
                                'avg_duration': {
                                    'avg': {'field': 'duration_seconds'}
                                }
                            }
                        }
                    }
                },
                'activity_timeline': {
                    'date_histogram': {
                        'field': '@timestamp',
                        'calendar_interval': '1h'
                    },
                    'aggs': {
                        'levels': {
                            'terms': {'field': 'level.keyword'}
                        }
                    }
                }
            },
            'size': 0
        }

        if service:
            query['query'] = {
                'bool': {
                    'must': [
                        query['query'],
                        {'term': {'service.keyword': service}}
                    ]
                }
            }

        result = es.search(
            index='chess-logs-*',
            body=query
        )

        # 格式化分析结果
        analysis = {
            'time_range': f"最近 {hours} 小时",
            'total_logs': result['hits']['total']['value'],
            'error_analysis': {
                'total_errors': result['aggregations']['error_analysis']['doc_count'],
                'error_types': [
                    {'type': b['key'], 'count': b['doc_count']}
                    for b in result['aggregations']['error_analysis']['error_types']['buckets']
                ],
                'error_services': [
                    {'service': b['key'], 'count': b['doc_count']}
                    for b in result['aggregations']['error_analysis']['error_services']['buckets']
                ]
            },
            'performance_analysis': {
                'total_operations': result['aggregations']['performance_analysis']['doc_count'],
                'avg_duration': result['aggregations']['performance_analysis']['avg_duration']['value'],
                'slow_functions': [
                    {
                        'function': b['key'],
                        'avg_duration': b['avg_duration']['value'],
                        'count': b['doc_count']
                    }
                    for b in result['aggregations']['performance_analysis']['slow_functions']['buckets']
                ]
            },
            'activity_timeline': [
                {
                    'timestamp': b['key_as_string'],
                    'total': b['doc_count'],
                    'levels': {
                        level_b['key']: level_b['doc_count']
                        for level_b in b['levels']['buckets']
                    }
                }
                for b in result['aggregations']['activity_timeline']['buckets']
            ]
        }

        return jsonify(analysis)

    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': '生成分析报告失败'
        }), 500


@app.route('/api/logs/services', methods=['GET'])
def get_services():
    """获取可用的服务列表"""
    try:
        es = get_elasticsearch_client()
        if es is None:
            # 默认服务列表
            return jsonify({
                'services': [
                    'web_gateway', 'vision_service', 'robot_service',
                    'ai_service', 'game_manager', 'calibration_service'
                ]
            })

        # 从Elasticsearch获取服务列表
        query = {
            'aggs': {
                'services': {
                    'terms': {'field': 'service.keyword', 'size': 100}
                }
            },
            'size': 0
        }

        result = es.search(
            index='chess-logs-*',
            body=query
        )

        services = [
            bucket['key'] for bucket in result['aggregations']['services']['buckets']
        ]

        return jsonify({'services': services})

    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': '获取服务列表失败'
        }), 500


if __name__ == '__main__':
    # 启动服务
    port = int(os.getenv('PORT', 8090))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    print(f"启动日志分析服务，端口: {port}")
    print(f"Elasticsearch: {os.getenv('ELASTICSEARCH_HOST', 'localhost')}:{os.getenv('ELASTICSEARCH_PORT', '9200')}")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
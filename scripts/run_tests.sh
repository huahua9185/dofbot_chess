#!/bin/bash

# 测试运行脚本
# 用于运行各种类型的测试

set -e  # 出错时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查虚拟环境
check_venv() {
    if [[ -z "$VIRTUAL_ENV" ]]; then
        log_warning "未检测到虚拟环境，尝试激活..."
        if [[ -f "venv/bin/activate" ]]; then
            source venv/bin/activate
            log_success "虚拟环境已激活"
        else
            log_error "找不到虚拟环境，请先运行 python -m venv venv && source venv/bin/activate"
            exit 1
        fi
    else
        log_info "已在虚拟环境中: $VIRTUAL_ENV"
    fi
}

# 安装测试依赖
install_test_deps() {
    log_info "安装测试依赖..."
    pip install -q pytest pytest-asyncio pytest-mock pytest-cov
    pip install -q httpx  # For FastAPI testing
    log_success "测试依赖安装完成"
}

# 运行单元测试
run_unit_tests() {
    log_info "运行单元测试..."

    local test_args="$1"
    local coverage_args=""

    if [[ "$test_args" == *"--coverage"* ]]; then
        coverage_args="--cov=services --cov=shared --cov-report=html --cov-report=term"
        test_args="${test_args/--coverage/}"
    fi

    pytest tests/unit/ \
        $coverage_args \
        -v \
        --tb=short \
        --durations=10 \
        $test_args

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "单元测试通过"
    else
        log_error "单元测试失败"
        return $exit_code
    fi
}

# 运行集成测试
run_integration_tests() {
    log_info "运行集成测试..."

    # 检查必要的服务是否运行
    if ! pgrep -f redis-server > /dev/null; then
        log_warning "Redis服务未运行，尝试启动..."
        redis-server --daemonize yes || {
            log_error "无法启动Redis服务"
            return 1
        }
    fi

    pytest tests/integration/ \
        -v \
        --tb=short \
        -m "not hardware" \
        "$1"

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "集成测试通过"
    else
        log_error "集成测试失败"
        return $exit_code
    fi
}

# 运行硬件测试
run_hardware_tests() {
    log_warning "运行硬件测试（需要连接硬件设备）..."

    # 检查硬件设备
    if [[ ! -e "/dev/ttyUSB0" ]] && [[ ! -e "/dev/ttyACM0" ]]; then
        log_error "未检测到串口设备，跳过硬件测试"
        return 0
    fi

    pytest tests/unit/ tests/integration/ \
        -v \
        --tb=short \
        -m "hardware" \
        "$1"

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "硬件测试通过"
    else
        log_error "硬件测试失败"
        return $exit_code
    fi
}

# 运行性能测试
run_performance_tests() {
    log_info "运行性能测试..."

    pytest tests/ \
        -v \
        --tb=short \
        -m "slow" \
        --durations=0 \
        "$1"

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "性能测试通过"
    else
        log_error "性能测试失败"
        return $exit_code
    fi
}

# 运行所有测试
run_all_tests() {
    log_info "运行所有测试..."

    local failed_tests=()

    # 单元测试
    if ! run_unit_tests "--coverage"; then
        failed_tests+=("单元测试")
    fi

    # 集成测试
    if ! run_integration_tests; then
        failed_tests+=("集成测试")
    fi

    # 性能测试
    if ! run_performance_tests; then
        failed_tests+=("性能测试")
    fi

    # 汇总结果
    if [[ ${#failed_tests[@]} -eq 0 ]]; then
        log_success "所有测试通过！"
        return 0
    else
        log_error "以下测试失败: ${failed_tests[*]}"
        return 1
    fi
}

# 生成测试报告
generate_report() {
    log_info "生成测试报告..."

    local report_dir="reports/test_results"
    mkdir -p "$report_dir"

    # 运行测试并生成报告
    pytest tests/unit/ \
        --cov=services \
        --cov=shared \
        --cov-report=html:"$report_dir/coverage" \
        --cov-report=xml:"$report_dir/coverage.xml" \
        --junit-xml="$report_dir/junit.xml" \
        -v

    log_success "测试报告已生成到 $report_dir"
    log_info "覆盖率报告: file://$PROJECT_ROOT/$report_dir/coverage/index.html"
}

# 清理测试环境
cleanup() {
    log_info "清理测试环境..."

    # 删除临时文件
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true

    # 停止测试数据库
    if pgrep -f "redis-server.*test" > /dev/null; then
        pkill -f "redis-server.*test"
    fi

    log_success "清理完成"
}

# 检查代码质量
check_code_quality() {
    log_info "检查代码质量..."

    # 检查是否安装了质量检查工具
    if ! command -v flake8 &> /dev/null; then
        log_warning "安装代码质量检查工具..."
        pip install -q flake8 black isort
    fi

    # 代码格式检查
    log_info "检查代码格式..."
    black --check --diff services/ shared/ tests/ || {
        log_error "代码格式不符合规范，运行 'black services/ shared/ tests/' 修复"
        return 1
    }

    # 导入排序检查
    log_info "检查导入排序..."
    isort --check-only --diff services/ shared/ tests/ || {
        log_error "导入排序不正确，运行 'isort services/ shared/ tests/' 修复"
        return 1
    }

    # 代码风格检查
    log_info "检查代码风格..."
    flake8 services/ shared/ tests/ || {
        log_error "代码风格检查失败"
        return 1
    }

    log_success "代码质量检查通过"
}

# 显示帮助信息
show_help() {
    cat << EOF
测试运行脚本

用法: $0 [选项] [测试类型]

测试类型:
  unit          运行单元测试
  integration   运行集成测试
  hardware      运行硬件测试 (需要硬件设备)
  performance   运行性能测试
  all           运行所有测试
  quality       检查代码质量

选项:
  --coverage    生成覆盖率报告
  --report      生成详细测试报告
  --clean       清理测试环境
  --verbose     详细输出
  --help        显示此帮助信息

示例:
  $0 unit --coverage          # 运行单元测试并生成覆盖率报告
  $0 integration              # 运行集成测试
  $0 all --report             # 运行所有测试并生成报告
  $0 --clean                  # 清理测试环境
  $0 quality                  # 检查代码质量

EOF
}

# 主函数
main() {
    local test_type=""
    local extra_args=""

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --clean)
                cleanup
                exit 0
                ;;
            --coverage)
                extra_args="$extra_args --coverage"
                shift
                ;;
            --report)
                generate_report
                exit 0
                ;;
            --verbose|-v)
                extra_args="$extra_args -v"
                shift
                ;;
            unit|integration|hardware|performance|all|quality)
                test_type="$1"
                shift
                ;;
            *)
                extra_args="$extra_args $1"
                shift
                ;;
        esac
    done

    # 如果没有指定测试类型，默认运行单元测试
    if [[ -z "$test_type" ]]; then
        test_type="unit"
    fi

    # 检查虚拟环境
    check_venv

    # 安装测试依赖
    install_test_deps

    # 运行对应的测试
    case "$test_type" in
        unit)
            run_unit_tests "$extra_args"
            ;;
        integration)
            run_integration_tests "$extra_args"
            ;;
        hardware)
            run_hardware_tests "$extra_args"
            ;;
        performance)
            run_performance_tests "$extra_args"
            ;;
        all)
            run_all_tests "$extra_args"
            ;;
        quality)
            check_code_quality
            ;;
        *)
            log_error "未知的测试类型: $test_type"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
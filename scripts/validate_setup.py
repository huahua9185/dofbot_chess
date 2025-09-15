#!/usr/bin/env python3
"""
项目设置验证脚本
"""
import os
import sys
import importlib.util
from pathlib import Path

def check_python_imports():
    """检查关键Python模块是否能正常导入"""
    required_modules = [
        'asyncio',
        'dataclasses',
        'json',
        'logging',
        'pathlib',
        'typing',
        'enum'
    ]

    print("🐍 检查Python模块导入...")
    failed = []

    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module}")
            failed.append(module)

    if failed:
        print(f"❌ 导入失败的模块: {failed}")
        return False

    print("✅ 所有核心Python模块导入成功")
    return True

def check_project_structure():
    """检查项目结构"""
    print("📁 检查项目结构...")

    required_files = [
        'shared/utils/logger.py',
        'shared/utils/redis_client.py',
        'shared/models/chess_models.py',
        'shared/config/settings.py',
        'README.md',
        'CLAUDE.md',
        '.env.example'
    ]

    required_dirs = [
        'services/vision_service/src',
        'services/robot_control_service/src',
        'services/ai_engine_service/src',
        'services/game_manager_service/src',
        'services/web_gateway_service/src',
        'infrastructure/docker',
        'tests/unit',
        'logs',
        'models',
        'calibration'
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
            print(f"  ❌ {file_path}")
        else:
            print(f"  ✅ {file_path}")

    missing_dirs = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)
            print(f"  ❌ {dir_path}/")
        else:
            print(f"  ✅ {dir_path}/")

    if missing_files or missing_dirs:
        print(f"❌ 缺失文件: {missing_files}")
        print(f"❌ 缺失目录: {missing_dirs}")
        return False

    print("✅ 项目结构完整")
    return True

def check_shared_modules():
    """检查共享模块是否可以导入"""
    print("📦 检查共享模块...")

    sys.path.insert(0, str(Path.cwd()))

    modules_to_test = [
        'shared.utils.logger',
        'shared.utils.redis_client',
        'shared.models.chess_models',
        'shared.config.settings'
    ]

    failed = []
    for module in modules_to_test:
        try:
            importlib.import_module(module)
            print(f"  ✅ {module}")
        except Exception as e:
            print(f"  ❌ {module}: {e}")
            failed.append(module)

    if failed:
        print(f"❌ 模块导入失败: {failed}")
        return False

    print("✅ 所有共享模块导入成功")
    return True

def check_configuration():
    """检查配置是否正确"""
    print("⚙️  检查配置...")

    try:
        from shared.config.settings import get_settings
        settings = get_settings()

        print(f"  ✅ 配置加载成功")
        print(f"  - 服务名称: {settings.service_name}")
        print(f"  - 环境: {settings.environment}")
        print(f"  - 调试模式: {settings.debug}")

        return True
    except Exception as e:
        print(f"  ❌ 配置加载失败: {e}")
        return False

def main():
    """主验证函数"""
    print("=== 智能象棋机器人项目设置验证 ===\n")

    checks = [
        ("Python模块", check_python_imports),
        ("项目结构", check_project_structure),
        ("共享模块", check_shared_modules),
        ("配置系统", check_configuration)
    ]

    results = []
    for name, check_func in checks:
        print(f"\n{'='*50}")
        success = check_func()
        results.append((name, success))
        print(f"{'='*50}")

    print(f"\n{'='*50}")
    print("📊 验证结果汇总:")
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  - {name}: {status}")
        if not passed:
            all_passed = False

    print(f"{'='*50}")
    if all_passed:
        print("🎉 所有检查通过！项目基础设施配置正确。")
        print("\n下一步:")
        print("1. 运行 ./scripts/setup_jetson_env.sh 安装依赖")
        print("2. 复制 .env.example 到 .env 并配置")
        print("3. 开始开发具体功能模块")
        return 0
    else:
        print("⚠️  部分检查失败，请修复后重试。")
        return 1

if __name__ == "__main__":
    exit(main())
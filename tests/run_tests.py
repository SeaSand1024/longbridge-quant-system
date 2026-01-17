"""
测试运行脚本
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_config import TestEnvironment
from tests.utils.test_helpers import TestHelpers


def setup_test_environment():
    """设置测试环境"""
    print("🚀 设置测试环境...")
    
    # 验证测试环境
    issues = TestHelpers.validate_test_environment()
    if issues:
        print("❌ 测试环境验证失败:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    
    # 设置测试环境
    test_env = TestEnvironment()
    test_env.setup()
    
    return True


def run_tests(test_type="all", markers=None, verbose=False, coverage=False):
    """运行测试"""
    print(f"🧪 运行测试: {test_type}")
    
    # 构建pytest命令
    cmd = ["python", "-m", "pytest"]
    
    # 添加测试路径
    if test_type == "all":
        cmd.append("tests/")
    elif test_type == "api":
        cmd.append("tests/api/")
    elif test_type == "frontend":
        cmd.append("tests/frontend/")
    elif test_type == "database":
        cmd.append("tests/database/")
    elif test_type == "integration":
        cmd.append("tests/integration/")
    else:
        cmd.append(f"tests/{test_type}")
    
    # 添加标记过滤
    if markers:
        cmd.extend(["-m", markers])
    
    # 添加详细输出
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # 添加覆盖率
    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing"
        ])
    
    # 添加其他选项
    cmd.extend([
        "--tb=short",
        "--strict-markers",
        "--html=reports/report.html",
        "--self-contained-html"
    ])
    
    # 运行测试
    try:
        result = subprocess.run(cmd, cwd=project_root, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 运行测试失败: {e}")
        return False


def cleanup_test_environment():
    """清理测试环境"""
    print("🧹 清理测试环境...")
    
    test_env = TestEnvironment()
    test_env.teardown()
    
    # 清理测试文件
    TestHelpers.cleanup_test_files()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行量化交易系统测试")
    
    parser.add_argument(
        "test_type",
        nargs="?",
        default="all",
        choices=["all", "api", "frontend", "database", "integration", "unit"],
        help="测试类型"
    )
    
    parser.add_argument(
        "-m", "--markers",
        help="pytest标记过滤器"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="生成覆盖率报告"
    )
    
    parser.add_argument(
        "--no-setup",
        action="store_true",
        help="跳过环境设置"
    )
    
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="跳过环境清理"
    )
    
    args = parser.parse_args()
    
    success = True
    
    try:
        # 设置测试环境
        if not args.no_setup:
            if not setup_test_environment():
                return 1
        
        # 运行测试
        success = run_tests(
            test_type=args.test_type,
            markers=args.markers,
            verbose=args.verbose,
            coverage=args.coverage
        )
        
        # 生成测试报告摘要
        if success:
            print("✅ 所有测试通过!")
        else:
            print("❌ 部分测试失败!")
        
        print(f"📊 测试报告: {project_root}/reports/report.html")
        
        if args.coverage:
            print(f"📈 覆盖率报告: {project_root}/htmlcov/index.html")
    
    finally:
        # 清理测试环境
        if not args.no_cleanup:
            cleanup_test_environment()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
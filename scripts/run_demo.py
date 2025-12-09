#!/usr/bin/env python3
"""
运行演示脚本

运行pm-mem的各种演示。
"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_basic_demo():
    """运行基本演示"""
    print("运行基本用法演示...")
    from examples.basic_usage import basic_usage_example, using_real_llm_example
    basic_usage_example()
    using_real_llm_example()


def run_workflow_demo():
    """运行工作流程演示"""
    print("运行完整工作流程演示...")
    from examples.demo_workflow import demo_workflow
    demo_workflow()


def run_tests():
    """运行测试"""
    print("运行测试...")
    import pytest
    exit_code = pytest.main(["tests/", "-v"])
    return exit_code == 0


def run_specific_test(test_path):
    """运行特定测试"""
    print(f"运行测试: {test_path}")
    import pytest
    exit_code = pytest.main([test_path, "-v"])
    return exit_code == 0


def list_demos():
    """列出所有演示"""
    print("可用的演示:")
    print("1. basic     - 基本用法演示 (examples/basic_usage.py)")
    print("2. workflow  - 完整工作流程演示 (examples/demo_workflow.py)")
    print("3. tests     - 运行所有测试")
    print("4. test-unit - 运行单元测试")
    print("5. test-integration - 运行集成测试")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行pm-mem演示和测试")
    parser.add_argument(
        "demo",
        nargs="?",
        default="list",
        help="要运行的演示名称 (basic, workflow, tests, test-unit, test-integration)",
    )
    parser.add_argument(
        "--test",
        help="运行特定测试文件",
    )

    args = parser.parse_args()

    # 确保在项目根目录
    os.chdir(project_root)

    if args.test:
        success = run_specific_test(args.test)
        sys.exit(0 if success else 1)

    demo_map = {
        "basic": run_basic_demo,
        "workflow": run_workflow_demo,
        "tests": run_tests,
        "test-unit": lambda: run_specific_test("tests/unit"),
        "test-integration": lambda: run_specific_test("tests/integration"),
    }

    if args.demo == "list":
        list_demos()
    elif args.demo in demo_map:
        try:
            demo_map[args.demo]()
        except KeyboardInterrupt:
            print("\n演示被用户中断")
            sys.exit(1)
        except Exception as e:
            print(f"运行演示时出错: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print(f"未知的演示: {args.demo}")
        list_demos()
        sys.exit(1)


if __name__ == "__main__":
    main()
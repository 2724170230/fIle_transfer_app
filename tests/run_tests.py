#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest
import argparse
import time

def run_tests(test_type=None, verbosity=2):
    """运行测试套件
    
    参数:
        test_type: 测试类型，可以是'unit', 'integration', 'performance'或None(运行所有测试)
        verbosity: 测试输出详细程度
    
    返回:
        测试结果对象
    """
    # 确保tests目录被添加到路径
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    
    # 确保项目根目录被添加到路径
    project_dir = os.path.dirname(tests_dir)
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 根据测试类型添加测试
    if test_type is None or test_type == 'unit':
        # 添加单元测试
        print("添加单元测试...")
        unit_tests = unittest.defaultTestLoader.discover(
            tests_dir, pattern="test_[a-z]*.py", 
            top_level_dir=tests_dir
        )
        test_suite.addTests(unit_tests)
    
    if test_type is None or test_type == 'integration':
        # 添加集成测试
        print("添加集成测试...")
        import test_integration
        test_suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(test_integration))
    
    if test_type is None or test_type == 'performance':
        # 添加性能测试
        print("添加性能测试...")
        import test_performance
        test_suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(test_performance))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(test_suite)
    
    return result

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行SendNow应用的测试套件")
    
    parser.add_argument(
        '--type', '-t', 
        choices=['unit', 'integration', 'performance', 'all'],
        default='all',
        help='要运行的测试类型'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='输出详细的测试信息'
    )
    
    args = parser.parse_args()
    
    # 设置测试类型
    test_type = None if args.type == 'all' else args.type
    
    # 设置详细程度
    verbosity = 2 if args.verbose else 1
    
    # 运行测试
    print(f"开始运行测试: {args.type}...")
    start_time = time.time()
    
    result = run_tests(test_type, verbosity)
    
    # 打印统计信息
    time_taken = time.time() - start_time
    print(f"\n测试完成，用时 {time_taken:.2f} 秒")
    print(f"总计: {result.testsRun} 个测试")
    print(f"成功: {result.testsRun - len(result.errors) - len(result.failures)} 个测试")
    print(f"失败: {len(result.failures)} 个测试")
    print(f"错误: {len(result.errors)} 个测试")
    
    # 设置退出码
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(main()) 
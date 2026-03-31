"""
简化版测试脚本 - 学习模块
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from learning_module import ResearchAnalyzer, LiteratureAnalyzer, ImprovementGenerator

print("测试开始...")

try:
    print("\n1. 测试ResearchAnalyzer初始化...")
    researcher = ResearchAnalyzer(api_provider='qwen', test_mode=True)
    print("   ✓ ResearchAnalyzer初始化成功")
except Exception as e:
    print(f"   ✗ ResearchAnalyzer初始化失败: {e}")

try:
    print("\n2. 测试LiteratureAnalyzer初始化...")
    analyzer = LiteratureAnalyzer(api_provider='qwen', test_mode=True)
    print("   ✓ LiteratureAnalyzer初始化成功")
except Exception as e:
    print(f"   ✗ LiteratureAnalyzer初始化失败: {e}")

try:
    print("\n3. 测试ImprovementGenerator初始化...")
    generator = ImprovementGenerator(api_provider='qwen', test_mode=True)
    print("   ✓ ImprovementGenerator初始化成功")
except Exception as e:
    print(f"   ✗ ImprovementGenerator初始化失败: {e}")

print("\n所有组件初始化测试完成！")

"""
学习模块快速开始脚本

演示如何使用学习模块进行NER模块优化。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 70)
print(" " * 15 + "学习模块 - NER优化快速开始")
print("=" * 70)

print("\n步骤1: 配置API密钥")
print("-" * 70)

api_key = os.environ.get('DASHSCOPE_API_KEY')
if api_key:
    print(f"✓ DASHSCOPE_API_KEY已配置: {api_key[:20]}...")
else:
    print("✗ DASHSCOPE_API_KEY未配置")
    print("  请设置环境变量: os.environ['DASHSCOPE_API_KEY'] = 'your-key'")

print("\n步骤2: 导入学习模块")
print("-" * 70)

try:
    from learning_module import LearningModule
    print("✓ LearningModule导入成功")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1)

print("\n步骤3: 初始化学习模块")
print("-" * 70)

try:
    learner = LearningModule(api_provider='qwen', test_mode=False)
    print("✓ 学习模块初始化成功")
    print(f"  - API Provider: qwen (通义千问)")
    print(f"  - Test Mode: False (实际API调用)")
except Exception as e:
    print(f"✗ 初始化失败: {e}")
    print("\n提示: 如果API密钥无效或网络问题，请使用test_mode=True:")
    print("  learner = LearningModule(api_provider='qwen', test_mode=True)")
    sys.exit(1)

print("\n步骤4: 执行NER模块优化分析")
print("-" * 70)

print("\n正在分析NER模块优化方案...")
print("(这将调用实际的API，可能需要几秒钟)\n")

try:
    result = learner.analyze_and_suggest(
        module_name='ner_processor',
        context='Japanese historical entity recognition in research documents',
        research_topic='Japanese Historical NER Deep Learning BERT'
    )
    
    print("✓ 分析完成!\n")
    
    print(f"模块: {result['module_name']}")
    print(f"上下文: {result['context']}")
    
    suggestions = result.get('improvement_suggestions', {})
    
    print("\n" + "=" * 70)
    print(" " * 20 + "优化建议")
    print("=" * 70)
    
    print("\n【短期改进】(1-2周)")
    for i, s in enumerate(suggestions.get('short_term_improvements', [])[:3], 1):
        print(f"  {i}. {s}")
    
    print("\n【中期改进】(1个月)")
    for i, s in enumerate(suggestions.get('medium_term_improvements', [])[:3], 1):
        print(f"  {i}. {s}")
    
    print("\n【长期改进】(3个月+)")
    for i, s in enumerate(suggestions.get('long_term_improvements', [])[:3], 1):
        print(f"  {i}. {s}")
    
    print(f"\n优先级: {suggestions.get('priority', 'N/A')}")
    
except Exception as e:
    print(f"✗ 分析失败: {e}")
    print("\n提示: 请检查API密钥和网络连接")
    sys.exit(1)

print("\n" + "=" * 70)
print(" " * 15 + "快速开始完成!")
print("=" * 70)
print("\n下一步:")
print("  1. 查看详细的优化方案: NER_MODULE_OPTIMIZATION_PLAN.md")
print("  2. 查看实施报告: NER_MODULE_OPTIMIZATION_REPORT.md")
print("  3. 使用学习模块进行其他优化:")
print("     from learning_module import LearningModule")
print("     learner = LearningModule(api_provider='qwen')")
print("     result = learner.analyze_and_suggest(module_name='your_module')")

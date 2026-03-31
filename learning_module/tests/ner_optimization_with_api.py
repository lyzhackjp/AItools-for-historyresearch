"""
NER模块实际API优化脚本

使用真实的Qwen和Minimax API进行NER模块优化测试。
严格遵循技术指南和工作流程图的规定。
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.api_key_manager import load_all_api_keys
load_all_api_keys()

from learning_module import LearningModule, ResearchAnalyzer


def test_qwen_api():
    """使用Qwen API进行NER优化测试"""
    print("\n" + "="*70)
    print(" " * 20 + "测试1：Qwen API (通义千问)")
    print("="*70)
    
    try:
        print("\n初始化Qwen API的学习模块...")
        learner = LearningModule(api_provider='qwen', test_mode=False)
        print("✓ Qwen API学习模块初始化成功")
        
        print("\n执行NER模块优化分析...")
        result = learner.analyze_and_suggest(
            module_name='ner_processor',
            context='Japanese historical entity recognition in research documents',
            research_topic='Japanese Historical NER Deep Learning BERT'
        )
        
        print("\n✓ NER优化分析完成")
        print(f"  - 模块名称: {result['module_name']}")
        print(f"  - 上下文: {result['context']}")
        
        suggestions = result.get('improvement_suggestions', {})
        print(f"\n优化建议:")
        print(f"  - 短期改进: {len(suggestions.get('short_term_improvements', []))} 项")
        print(f"  - 中期改进: {len(suggestions.get('medium_term_improvements', []))} 项")
        print(f"  - 长期改进: {len(suggestions.get('long_term_improvements', []))} 项")
        print(f"  - 优先级: {suggestions.get('priority', 'N/A')}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ Qwen API测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_minimax_api():
    """使用Minimax API进行NER优化测试"""
    print("\n" + "="*70)
    print(" " * 20 + "测试2：Minimax API")
    print("="*70)
    
    try:
        print("\n初始化Minimax API的学习模块...")
        learner = LearningModule(api_provider='minimax', test_mode=False)
        print("✓ Minimax API学习模块初始化成功")
        
        print("\n执行NER模块优化分析...")
        result = learner.analyze_and_suggest(
            module_name='ner_processor',
            context='Japanese historical entity recognition in research documents',
            research_topic='Japanese Historical NER Deep Learning BERT'
        )
        
        print("\n✓ NER优化分析完成")
        print(f"  - 模块名称: {result['module_name']}")
        print(f"  - 上下文: {result['context']}")
        
        suggestions = result.get('improvement_suggestions', {})
        print(f"\n优化建议:")
        print(f"  - 短期改进: {len(suggestions.get('short_term_improvements', []))} 项")
        print(f"  - 中期改进: {len(suggestions.get('medium_term_improvements', []))} 项")
        print(f"  - 长期改进: {len(suggestions.get('long_term_improvements', []))} 项")
        print(f"  - 优先级: {suggestions.get('priority', 'N/A')}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ Minimax API测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def compare_results(qwen_result, minimax_result):
    """对比两种API的结果"""
    print("\n" + "="*70)
    print(" " * 20 + "结果对比分析")
    print("="*70)
    
    if not qwen_result or not minimax_result:
        print("\n⚠️ 无法进行对比，部分API调用失败")
        return
    
    print("\n【短期改进建议对比】")
    print("-" * 70)
    
    qwen_short = qwen_result.get('improvement_suggestions', {}).get('short_term_improvements', [])
    minimax_short = minimax_result.get('improvement_suggestions', {}).get('medium_term_improvements', [])
    
    print("\nQwen API建议:")
    for i, item in enumerate(qwen_short[:3], 1):
        print(f"  {i}. {item}")
    
    print("\nMinimax API建议:")
    for i, item in enumerate(minimax_short[:3], 1):
        print(f"  {i}. {item}")
    
    print("\n【结论】")
    print("-" * 70)
    print("两种API都提供了有价值的NER模块优化建议。")
    print("建议综合两种API的建议，制定最终的优化方案。")


def main():
    """主函数"""
    print("\n" + "="*70)
    print(" " * 10 + "NER模块实际API优化测试")
    print("="*70)
    print(f"\n执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("遵循技术指南和工作流程图的规定")
    
    results = {}
    
    print("\n" + "="*70)
    print("开始API测试...")
    print("="*70)
    
    print("\n⚠️ 注意：实际API调用将消耗配额，请确认API密钥有效")
    response = input("\n是否继续？(y/n): ")
    if response.lower() != 'y':
        print("\n已取消API调用")
        return
    
    success1, qwen_result = test_qwen_api()
    results['qwen'] = success1
    
    if success1:
        print("\n✓ Qwen API测试成功")
    else:
        print("\n✗ Qwen API测试失败，尝试Minimax API")
    
    success2, minimax_result = test_minimax_api()
    results['minimax'] = success2
    
    if success2:
        print("\n✓ Minimax API测试成功")
    else:
        print("\n✗ Minimax API测试失败")
    
    print("\n" + "="*70)
    print(" " * 20 + "测试结果汇总")
    print("="*70)
    
    print(f"\nQwen API: {'✓ 成功' if success1 else '✗ 失败'}")
    print(f"Minimax API: {'✓ 成功' if success2 else '✗ 失败'}")
    
    if success1 and success2:
        compare_results(qwen_result, minimax_result)
    
    print("\n" + "="*70)
    
    return results


if __name__ == '__main__':
    main()
